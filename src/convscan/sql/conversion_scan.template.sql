-- Conversion scan queries (read-only): pre-scan, post-scan and ID map
-- Target: the Blackboard LMS reporting replica through Direct Data Access (PostgreSQL), or the
-- same SQL through the Reporting Framework.
-- Written 2026-11-12 against the DDA schema docs for 4001.2.0, then run and revised on the
-- demo.blackboard.com DDA (2026-11-13 to 2026-11-15, on 4001.7.0 from 2026-11-10):
--   * every table and column below exists on demo (checked through information_schema),
--   * every query ran on demo against a scope of courses with groups, release rules, tests,
--     pools, SCORM and forums.
--   A production site's build may differ from demo: run S0 (convscan check) first there, and
--   check the schema changes before each LMS release (README.md, "About DDA").
--
-- How to use (expanded and run by convscan, or printed with convscan sql):
--   * The SCOPE placeholder (in braces in each query) lists the courses to scan. Run the
--     S-queries once on the Originals (pre-scan, the baseline) and again on the converted
--     copies (post-scan), then compare the two result sets, matched with M1 and M2.
--     (Never write a placeholder with its braces in a comment: convscan replaces it
--     everywhere, and a multi-line scope inside a comment breaks the statement.)
--   * The PREFIX and SUFFIX placeholders are the new course ID rule: the copy's course_id
--     is the prefix, then the Original's course_id, then the suffix (both configurable, see
--     config.example.yaml; the prefix is empty by default).
--   * The PAIRS placeholder lists Original and copy course_ids side by side (the batch
--     manifest). Only M2 uses it.
--   * SELECT only. Learners appear as users_pk1 or course_users.pk1, never by name,
--     username or email. users_pk1 is the same in the Original and the copy.
--   * The LEARNERS placeholder narrows S7, S8b and S10 to the learners read one by one
--     (students in progress by default; see S7). It always follows a course_users join
--     aliased cu.
--   * S7, S8b, S10 and S12b return one row per learner (per item) and are the large ones.
--     Time of day doesn't matter: DDA is a read replica, so scans put no load on production.
--   * The replica lags production by a few minutes at most: wait a few minutes after a
--     copy or repair before the post-scan.
--
-- Code values (confirmed on demo 2026-11-13 unless marked):
--   attempt.status: 1 not attempted, 2 abandoned, 3 in progress, 4 suspended, 5 cancelled,
--     6 needs grading, 7 completed, 8 in more progress, 9 needs more grading.
--     Submitted = 6, 7, 9; open = 3, 4, 8. (Demo holds 1, 3, 6, 7, 9; the meanings are
--     Blackboard's AttemptStatus constants.)
--   course_users.row_status: 0 enabled, 2 disabled. course_users.role: 'S' student, 'P'
--     instructor, 'T' teaching assistant, 'B' course builder, 'G' grader, plus custom roles.
--   gradebook_main.calculated_ind: N not calculated; C, T, W, A, M calculated (average,
--     total, weighted, and so on). deleted_ind 'Y' columns are deleted and are excluded
--     everywhere (demo: 11,902 deleted against 13,710 live).
--   qti_asi_data: bbmd_asi_type 1 assessment, 2 section, 3 question.
--     bbmd_assessmenttype 1 test, 4 pool. bbmd_sectiontype 2 normal section, 3 and 4 random
--     block or question set (both seen; which is which is not needed here).
--     bbmd_partialcredit 'Y', 'N' or blank.
--   course_assessment.time_limit is in minutes. timer_completion is the Auto-Submit setting:
--     'C' = OFF (learner may continue after time expires), 'H' = ON (saves and submits when
--     time expires), blank = no timer. Both confirmed in the GUI on demo 2026-11-13
--     (WEBB_TEST_2024_3: "Advertising Vocabulary" is C, "Advertising General Concepts" is H).
--   SCORM Engine tables store Blackboard IDs as strings: '_' || pk1 || '_1'.


-- ===========================================================================
-- S0. Schema check: every table this kit reads, and the columns most likely to change (the
--     ones joins, filters and rules depend on). Run first on a new site and after each
--     LMS release. Returns only what is MISSING; zero rows means the kit should run.
-- ===========================================================================
with need(t, c) as (values
 ('course_main','course_id'),('course_main','ultra_status'),('course_main','available_ind'),('course_main','row_status'),
 ('course_users','role'),('course_users','available_ind'),('course_users','last_access_date'),('course_users','row_status'),
 ('course_contents','cnthndlr_handle'),('course_contents','available_ind'),('course_contents','main_data'),('course_contents','web_url'),
 ('course_contents','parent_pk1'),
 ('gradebook_main','calculated_ind'),('gradebook_main','visible_ind'),('gradebook_main','visible_in_book_ind'),('gradebook_main','deleted_ind'),
 ('gradebook_main','qti_asi_data_pk1'),('gradebook_main','course_contents_pk1'),('gradebook_main','user_created_ind'),
 ('gradebook_grade','manual_score'),('gradebook_grade','last_attempt_pk1'),('gradebook_grade','highest_attempt_pk1'),
 ('gradebook_grade','course_users_pk1'),('attempt','gradebook_grade_pk1'),('attempt','status'),
 ('avl_rule','course_contents_pk1'),
 ('avl_crit','avl_rule_pk1'),('avl_crit','crit_type'),('avl_crit','gradebook_main_pk1'),('avl_crit','negate_ind'),('avl_crit','reviewed_content_pk1'),
 ('avl_crit_acl_group','groups_pk1'),('avl_crit_acl_user','users_pk1'),
 ('groups','group_name'),('group_users','groups_pk1'),('group_users','course_users_pk1'),
 ('qti_asi_data','bbmd_asi_type'),('qti_asi_data','bbmd_assessmenttype'),('qti_asi_data','bbmd_partialcredit'),
 ('qti_asi_data','bbmd_questiontype'),('qti_asi_data','parent_pk1'),('qti_asi_data','data'),
 ('qti_block_mapping','question_block_pk1'),('qti_block_mapping','question_pk1'),
 ('course_assessment','time_limit'),('course_assessment','timer_completion'),('course_assessment','proctoring_service_handle'),
 ('course_assessment','req_secure_browser_take_ind'),('course_assessment','qti_asi_data_pk1'),
 ('system_registry','registry_key'),('system_registry','registry_value'),('user_test_option','course_users_pk1'),('user_test_option','groups_pk1'),
 ('scormpackage','api_course_id'),('scormregistration','api_registration_id'),('scormregistration','suspended_activity_id'),('scormregistration','runtime_data'),
 ('scormactivity','scorm_registration_id'),('scormactivityrt','location'),('scormactivityrt','suspend_data'),
 ('scormregistration','engine_tenant_id'),('scormactivity','engine_tenant_id'),('scormactivityrt','engine_tenant_id'),
 ('scormbbpackageinfo','max_attempts'),('scormbbgradebookinfo','gradebook_column_id'),('scormpackageproperties','time_limit'),
 ('conference_main','crsmain_pk1'),('forum_main','confmain_pk1'),('msg_main','forummain_pk1'),
 ('queued_tasks','task_type'),('queued_tasks','status'),('queued_tasks','course_main_pk1'),('queued_tasks','results'))
select n.t as table_name, n.c as column_name, 'MISSING' as status
from need n
left join information_schema.columns ic
  on ic.table_schema = 'public' and ic.table_name = n.t and ic.column_name = n.c
where ic.column_name is null
order by 1, 2;


-- ===========================================================================
-- S1. Course identity and status, with the expected new course ID
--     new_id_taken counts disabled courses too (an earlier test copy left disabled is
--     still a clash).
-- ===========================================================================
with scope as ({SCOPE})
select s.course_id, cm.pk1 as crs_pk, cm.course_name, cm.ultra_status, cm.available_ind, cm.row_status,
  cm.dtcreated, cm.dtmodified,
  '{PREFIX}' || s.course_id || '{SUFFIX}'                       as expected_new_course_id,
  length('{PREFIX}' || s.course_id || '{SUFFIX}')               as new_id_length,
  exists (select 1 from course_main x where x.course_id = '{PREFIX}' || s.course_id || '{SUFFIX}') as new_id_taken
from scope s
join course_main cm on cm.pk1 = s.crs_pk
order by s.course_id;


-- ===========================================================================
-- S2. Members: every role, and students in progress, completed and disabled, with last
--     access. An unavailable membership (available_ind 'N') means the learner has completed
--     or their access has expired; 'completed' below counts both. Disabled enrollments
--     (row_status 2) are counted separately. Copy and convert
--     KEEPS disabled members (observed 2026-11-13), so the copy load is members plus
--     students_disabled (plus any disabled staff). Left join, so a course with no members
--     still returns a row of zeros.
-- ===========================================================================
with scope as ({SCOPE})
select s.course_id,
  count(*) filter (where cu.row_status = 0)                                         as members,
  count(*) filter (where cu.row_status = 0 and cu.role <> 'S')                      as staff,
  count(*) filter (where cu.row_status = 0 and cu.role = 'S')                       as students,
  count(*) filter (where cu.row_status = 0 and cu.role = 'S' and cu.available_ind = 'Y') as in_progress,
  count(*) filter (where cu.row_status = 0 and cu.role = 'S' and cu.available_ind = 'N') as completed,
  count(*) filter (where cu.row_status <> 0 and cu.role = 'S')                      as students_disabled,
  count(*) filter (where cu.row_status = 0 and cu.role = 'S' and cu.available_ind = 'Y'
                     and cu.last_access_date >= now() - interval '30 days')         as ip_lt30d,
  count(*) filter (where cu.row_status = 0 and cu.role = 'S' and cu.available_ind = 'Y'
                     and cu.last_access_date <  now() - interval '90 days')         as ip_gt90d,
  count(*) filter (where cu.row_status = 0 and cu.role = 'S' and cu.available_ind = 'Y'
                     and cu.last_access_date is null)                               as ip_never
from scope s
left join course_users cu on cu.crsmain_pk1 = s.crs_pk
group by s.course_id
order by members desc;

-- S2b. Totals for the students the per-learner queries leave out. By default S7, S8b and S10
--      read only enabled, available students (in progress). Unavailable students (completed or
--      expired) and disabled students are copied the same way, so their records are totalled here
--      and the hand-off compares the totals without reading anyone's grades or SCORM state.
--      One row per course and state ('unavailable' or 'disabled'), only where there are any.
--      Grade rows exclude calculated and deleted columns, as in S7.
with scope as ({SCOPE}),
m as (
  select s.course_id, s.crs_pk, cu.pk1 as cu_pk, cu.users_pk1,
         case when cu.row_status <> 0 then 'disabled' else 'unavailable' end as state
  from scope s
  join course_users cu on cu.crsmain_pk1 = s.crs_pk and cu.role = 'S'
                      and (cu.row_status <> 0 or cu.available_ind = 'N')),
g as (
  select m.cu_pk, count(distinct gg.pk1) as grade_rows, count(a.pk1) as attempts,
         count(a.pk1) filter (where a.status in (3, 4, 8)) as open,
         count(a.pk1) filter (where a.status in (6, 9))    as needs_grading
  from m
  join gradebook_grade gg on gg.course_users_pk1 = m.cu_pk
  join gradebook_main gm  on gm.pk1 = gg.gradebook_main_pk1 and coalesce(gm.calculated_ind, 'N') = 'N'
                         and coalesce(gm.deleted_ind, 'N') = 'N'
  left join attempt a     on a.gradebook_grade_pk1 = gg.pk1
  group by m.cu_pk),
sc as (
  select m.cu_pk, count(*) as scorm_registrations
  from m
  join course_contents cc  on cc.crsmain_pk1 = m.crs_pk and cc.cnthndlr_handle = 'resource/x-plugin-scormengine'
  join scormpackage p      on p.api_course_id = '_' || cc.pk1 || '_1'
  join scormregistration r on r.scorm_package_id = p.scorm_package_id
                          and split_part(r.api_registration_id, '-', 2) = '_' || m.users_pk1 || '_1'
  group by m.cu_pk)
select m.course_id, m.state, count(*) as learners,
  coalesce(sum(g.grade_rows), 0)           as grade_rows,
  coalesce(sum(g.attempts), 0)             as attempts,
  coalesce(sum(g.open), 0)                 as open,
  coalesce(sum(g.needs_grading), 0)        as needs_grading,
  coalesce(sum(sc.scorm_registrations), 0) as scorm_registrations
from m
left join g  on g.cu_pk = m.cu_pk
left join sc on sc.cu_pk = m.cu_pk
group by m.course_id, m.state
order by m.course_id, m.state;


-- ===========================================================================
-- S3. Content inventory per course: handlers, SCORM, home-package candidates,
--     links to the Content Collection, LTI, items hidden from learners
-- ===========================================================================
with scope as ({SCOPE})
select s.course_id,
  count(*)                                                                         as items,
  count(*) filter (where cc.cnthndlr_handle in ('resource/x-plugin-scormengine', 'resource/x-plugin-scorm')) as scorm,
  count(*) filter (where cc.cnthndlr_handle = 'resource/x-plugin-scormengine'
                     and cc.title ~* '(course home|accueil|home ?page|page d.accueil)') as scorm_home_candidates,
  count(*) filter (where cc.cnthndlr_handle = 'resource/x-bb-asmt-test-link')      as tests,
  count(*) filter (where cc.cnthndlr_handle = 'resource/x-bb-assignment')          as assignments,
  count(*) filter (where cc.cnthndlr_handle = 'resource/x-bb-forumlink')           as forum_links,
  count(*) filter (where cc.cnthndlr_handle = 'resource/x-bb-courselink')          as course_links,
  count(*) filter (where cc.cnthndlr_handle = 'resource/x-bb-toollink')            as tool_links,
  count(*) filter (where cc.cnthndlr_handle like 'resource/x-bb-blti%')            as lti_items,
  count(*) filter (where cc.cnthndlr_handle in ('resource/x-bb-folder', 'resource/x-bb-lesson')) as containers,
  count(*) filter (where cc.available_ind = 'N')                                   as items_unavailable,
  count(*) filter (where cc.main_data ~ 'xid-[0-9]+_1' or cc.web_url like '%bbcswebdav%') as cc_references,
  count(*) filter (where cc.web_url ~* 'bbcswebdav.*\.html?($|\?)')                as cc_html_pages,   -- gap G8: fetch and check these
  count(*) filter (where cc.start_date is not null or cc.end_date is not null)     as dated_items
from scope s
join course_contents cc on cc.crsmain_pk1 = s.crs_pk
group by s.course_id
order by s.course_id;

-- S3c. Content types: every content handler in each course, with how many items are
--      hidden from learners. The rule table flags types not yet covered by conversion
--      testing, and the post-scan compares the two inventories.
with scope as ({SCOPE})
select s.course_id, cc.cnthndlr_handle, count(*) as items,
  count(*) filter (where cc.available_ind = 'N') as items_unavailable
from scope s
join course_contents cc on cc.crsmain_pk1 = s.crs_pk
group by s.course_id, cc.cnthndlr_handle
order by s.course_id, items desc;

-- S3b. Item list with title path (for matching items between Original and copy, M1).
--      Path is the chain of parent titles; conversion adds wrappers, so match on the
--      item's own title, handler and nearest parent title, not the full path.
with recursive scope as ({SCOPE}),
tree as (
  select s.course_id, cc.pk1, cc.parent_pk1, cc.title, cc.cnthndlr_handle, cc.available_ind,
         cc.web_url, cc.title::text as path, 0 as depth
  from scope s join course_contents cc on cc.crsmain_pk1 = s.crs_pk
  where cc.parent_pk1 is null
  union all
  select t.course_id, c.pk1, c.parent_pk1, c.title, c.cnthndlr_handle, c.available_ind,
         c.web_url, t.path || ' / ' || c.title, t.depth + 1
  from tree t join course_contents c on c.parent_pk1 = t.pk1)
select t.course_id, t.pk1 as content_pk, t.cnthndlr_handle, t.title, t.available_ind, t.depth, t.path,
  p.title as parent_title, t.web_url, t.parent_pk1 as parent_pk
from tree t
left join course_contents p on p.pk1 = t.parent_pk1
order by t.course_id, t.path;

-- S3d. Folders and learning modules nested too deep for the site's limit (S14, 3 levels if
--      unset, 4 with the additional nesting level), in Original courses only. A content area
--      becomes a top-level item in Ultra (level 1), so a container at depth d in the Original
--      lands at level d + 1. The limit counts levels of nested content, so a container needs a
--      level below it for its content: with 3 levels, a learning module (1) holds a folder (2),
--      whose content is level 3, and a folder at level 3 can't hold anything. Conversion moves
--      each such container up to sit directly in its learning module (level 2), with the items
--      directly in it; a too-deep container inside another comes out too, as its own folder
--      beside it (seen in conversion testing: every container at level 3 or deeper moved there,
--      every one at level 2 stayed). One row per container. items_here counts the items
--      directly in it, which move with it. moves_one_level_more is 1 when it would still be
--      too deep with one more level allowed (the additional nesting level).
with recursive scope as ({SCOPE}),
lim as (
  select coalesce(max(case when r.registry_value ~ '^[0-9]+$' then r.registry_value::int end), 3) as max_level
  from system_registry r
  where r.registry_key = 'course.structure.max_level_of_nesting'),
tree as (
  select s.course_id, cc.pk1, cc.title, cc.cnthndlr_handle, cc.title::text as path, 0 as depth
  from scope s
  join course_main cm     on cm.pk1 = s.crs_pk and coalesce(cm.ultra_status, 'C') = 'C'
  join course_contents cc on cc.crsmain_pk1 = s.crs_pk
  where cc.parent_pk1 is null
  union all
  select t.course_id, c.pk1, c.title, c.cnthndlr_handle, t.path || ' / ' || c.title, t.depth + 1
  from tree t join course_contents c on c.parent_pk1 = t.pk1),
deep as (
  select t.*, l.max_level
  from tree t
  cross join lim l
  where t.cnthndlr_handle in ('resource/x-bb-folder', 'resource/x-bb-lesson')
    and t.depth + 1 >= l.max_level)
select d.course_id, d.pk1 as content_pk, d.cnthndlr_handle, d.title, d.path,
  d.depth + 1 as ultra_level, d.max_level,
  coalesce(b.items_here, 0) as items_here,
  case when d.depth + 1 >= d.max_level + 1 then 1 else 0 end as moves_one_level_more,
  d.path || ' (' || coalesce(b.items_here, 0) || ' item(s))' as label
from deep d
left join lateral (
  select count(*) as items_here
  from course_contents u
  where u.parent_pk1 = d.pk1 and u.cnthndlr_handle not in ('resource/x-bb-folder', 'resource/x-bb-lesson')) b on true
order by d.course_id, d.path;


-- ===========================================================================
-- S4. Gradebook columns: type, attached item, visibility, calculated, orphans
--     (columns tracked by an outside system are joined afterwards from its own list).
--     Deleted columns are excluded.
-- ===========================================================================
with scope as ({SCOPE}),
grades as (
  select gg.gradebook_main_pk1 as col_pk, count(*) as grade_rows
  from scope s
  join gradebook_main gm  on gm.crsmain_pk1 = s.crs_pk and coalesce(gm.deleted_ind, 'N') = 'N'
  join gradebook_grade gg on gg.gradebook_main_pk1 = gm.pk1
  group by gg.gradebook_main_pk1)
select s.course_id, gm.pk1 as col_pk, gm.title, gm.display_title, gm.score_provider_handle,
  gm.course_contents_pk1 as content_pk, cc.title as content_title, p.title as content_parent_title,
  gm.calculated_ind, gm.scorable_ind, gm.possible, gm.aggregation_model,
  gm.visible_ind, gm.visible_in_book_ind,           -- 'N' = hidden from students today
  gm.single_attempt_ind, gm.multiple_attempts,
  gm.qti_asi_data_pk1,
  (gm.course_contents_pk1 is null and coalesce(gm.calculated_ind, 'N') = 'N'
     and coalesce(gm.user_created_ind, 'N') = 'N')                     as orphan_candidate,
  count(*) over (partition by s.course_id, lower(trim(gm.title)))     as same_title_count,
  coalesce(g.grade_rows, 0)                                           as grade_rows
from scope s
join gradebook_main gm on gm.crsmain_pk1 = s.crs_pk and coalesce(gm.deleted_ind, 'N') = 'N'
left join course_contents cc on cc.pk1 = gm.course_contents_pk1
left join course_contents p  on p.pk1 = cc.parent_pk1
left join grades g           on g.col_pk = gm.pk1
order by s.course_id, gm.position, gm.pk1;


-- ===========================================================================
-- S5b. Partial-credit questions per course, by how their tests are used.
--     Conversion sets partial credit to 0% on every answer except the correct one
--     (observed 2026-11-10). Scores already earned are kept; new attempts score lower.
--     REMEDIATION (adopted 2026-11-12): fix ALL partial-credit questions. They are
--     tier 1 only where the test gates or otherwise controls progress, and then only for
--     learners who haven't taken it yet. Everything else is tier 2.
--       routing   : test read by 2+ distinct score ranges (a score selector)      -> tier 1
--       gate      : test read by a score criterion (pass mark opens the next step)  -> tier 1
--       graded    : test counts for a grade but gates nothing                       -> tier 2
--     QUESTION SOURCES (confirmed on demo 2026-11-13):
--       direct    : question (asi_type 3) -> section (2) -> test (1, the column's qti_asi_data_pk1)
--       via block : a random block or question set sits at question level in the test's
--                   section, and qti_block_mapping links it to the questions it draws from, in
--                   a pool (assessmenttype 4) or another test (for example an "ALL QUESTIONS"
--                   test). On demo the direct route alone missed 565 questions in 75 tests.
--     LIMIT: a test that gates only through a calculated column (for example a "Module Score"
--     that is the maximum of a test and an always-zero column) counts as graded here. The
--     calculated_gates rule (S9) flags those courses.
--     (Labeled S5b because an earlier per-question S5 was retired: S5c has the detail.)
-- ===========================================================================
with scope as ({SCOPE}),
tests as (
  select s.course_id, gm.pk1 as col_pk, gm.qti_asi_data_pk1 as asmt_pk
  from scope s
  join gradebook_main gm on gm.crsmain_pk1 = s.crs_pk and gm.qti_asi_data_pk1 is not null
                        and coalesce(gm.deleted_ind, 'N') = 'N'),
questions as (
  select t.col_pk, q.pk1 as question_pk, 'direct' as source
  from tests t
  join qti_asi_data sec on sec.parent_pk1 = t.asmt_pk
  join qti_asi_data q   on q.parent_pk1 = sec.pk1 and q.bbmd_partialcredit = 'Y'
  union all
  select t.col_pk, pq.pk1, 'via block'
  from tests t
  join qti_asi_data sec on sec.parent_pk1 = t.asmt_pk
  join qti_asi_data blk on blk.parent_pk1 = sec.pk1
  join qti_block_mapping m on m.question_block_pk1 = blk.pk1
  join qti_asi_data pq  on pq.pk1 = m.question_pk1 and pq.bbmd_partialcredit = 'Y'),
score_use as (
  select ac.gradebook_main_pk1 as col_pk,
         count(distinct (ac.min_score, ac.max_score)) filter (where ac.crit_type like 'GRADE_RANGE%') as ranges
  from avl_crit ac
  where ac.gradebook_main_pk1 in (select col_pk from tests)
  group by ac.gradebook_main_pk1)
select t.course_id,
  count(distinct t.col_pk)                                                      as tests_with_partial_credit,
  count(distinct q.question_pk)                                                 as partial_credit_questions,
  count(distinct q.question_pk) filter (where q.source = 'via block')           as from_pools_or_sets,
  count(distinct q.question_pk) filter (where coalesce(u.ranges, 0) >= 2)       as in_routing_tests,
  count(distinct q.question_pk) filter (where coalesce(u.ranges, 0) = 1)        as in_gating_tests,
  count(distinct q.question_pk) filter (where coalesce(u.ranges, 0) = 0)        as in_graded_only_tests
from tests t
join questions q      on q.col_pk = t.col_pk
left join score_use u on u.col_pk = t.col_pk
group by t.course_id
order by partial_credit_questions desc;

-- S5c. Answer weights for every partial-credit question (the repair list and its baseline).
--      The partial-credit switch alone overstates the work: on demo many switched-on questions
--      give every wrong answer 0%, so conversion changes nothing for them. This reads each
--      answer's weight from the question XML (qti_asi_data.data) and keeps the result per
--      question:
--        weights        : answer letter (display order) and weight, % of the question's points,
--                         for example "A 100 | B 80 | C 60 | D 0"
--        real_partial   : true when any answer is worth more than 0% and less than 100%: these
--                         are the questions conversion damages
--        weights_found  : 0 means the type gives proportional credit (Matching, Jumbled
--                         Sentence, Fill in the Blank Plus, Calculated, and Ordering, which
--                         Ultra removes on conversion, see S5d): no weight per
--                         answer, the switch is the whole setting. scoring_note says so. Check on
--                         a test conversion whether that switch survives.
--      On demo (2026-11-13): 1,268 switched-on questions in live tests, 310 with real partial
--      weights, about 760 proportional types. Multiple Answer and Multiple Choice carry weights.
--      (Comment lines in this file must never end in a semicolon: tools that split the file on
--      semicolons would cut the statement there.)
--      XML layout confirmed on demo 2026-11-13: each answer is a <response_label ident="...">,
--      and its weight is a <respcondition> whose <varequal respident="<ident>"/> is followed by
--      <setvar variablename="SCORE">pct</setvar>. Weights are percentages.
--      REMEDY: Ultra's public REST API reads and updates a test's questions and answers, so the
--      repair on the copy is a REST script driven by this list (only the real_partial rows),
--      and the post-scan reruns S5c on the copy to prove the weights are back.
--      Run on the copy too: after conversion the same questions should show all wrong answers 0.
with scope as ({SCOPE}),
tests as (
  select s.course_id, gm.pk1 as col_pk, gm.title as test_title, gm.qti_asi_data_pk1 as asmt_pk
  from scope s
  join gradebook_main gm on gm.crsmain_pk1 = s.crs_pk and gm.qti_asi_data_pk1 is not null
                        and coalesce(gm.deleted_ind, 'N') = 'N'),
questions as (
  select t.col_pk, q.pk1 as question_pk, 'direct' as source
  from tests t
  join qti_asi_data sec on sec.parent_pk1 = t.asmt_pk
  join qti_asi_data q   on q.parent_pk1 = sec.pk1 and q.bbmd_partialcredit = 'Y'
  union all
  select t.col_pk, pq.pk1, 'via block'
  from tests t
  join qti_asi_data sec on sec.parent_pk1 = t.asmt_pk
  join qti_asi_data blk on blk.parent_pk1 = sec.pk1
  join qti_block_mapping m on m.question_block_pk1 = blk.pk1
  join qti_asi_data pq  on pq.pk1 = m.question_pk1 and pq.bbmd_partialcredit = 'Y'),
qx as (                                              -- each question once, with its XML
  select distinct q.question_pk, convert_from(qq.data, 'UTF8') as x
  from questions q join qti_asi_data qq on qq.pk1 = q.question_pk),
labels as (                                          -- answers in display order
  select qx.question_pk, l.ord, l.m[1] as ident,
         left(trim(regexp_replace(regexp_replace(
           replace(replace(replace(replace(
             regexp_replace(                         -- drop the tag's attributes (type="HTML">)
               split_part(split_part(split_part(qx.x, '<response_label ident="' || l.m[1] || '"', 2),
                                     '</response_label>', 1), '<mat_formattedtext', 2),
               '^[^>]*>', ''),
             '&lt;', '<'), '&gt;', '>'), '&amp;nbsp;', ' '), '&amp;', '&'),
           '<[^>]*>', '', 'g'), '\s+', ' ', 'g')), 40) as answer_text
  from qx, regexp_matches(qx.x, '<response_label ident="([^"]+)"', 'g') with ordinality as l(m, ord)),
weights as (
  select qx.question_pk, w.m[1] as ident, w.m[2]::numeric as pct
  from qx, regexp_matches(qx.x,
         '<varequal respident="([^"]+)"[^>]*/>\s*</conditionvar>\s*<setvar variablename="SCORE" action="Set">(-?[0-9.]+)</setvar>',
         'g') as w(m)),
per_q as (
  select l.question_pk,
         count(*)                                                      as answers,
         count(w.pct)                                                  as weights_found,
         bool_or(w.pct > 0 and w.pct < 100)                            as real_partial,
         string_agg(chr(64 + l.ord::int) || ' ' || coalesce((w.pct::float8)::text, '?'),
                    ' | ' order by l.ord)                              as weights,
         string_agg(chr(64 + l.ord::int) || ' ' || l.answer_text, ' | ' order by l.ord) as answers_text
  from labels l
  left join weights w on w.question_pk = l.question_pk and w.ident = l.ident
  group by l.question_pk)
select t.course_id, t.col_pk, t.test_title, q.source, qq.pk1 as question_pk, qq.title as question_title,
  substring(qx.x from '<bbmd_questiontype>([^<]*)')               as question_type,
  qq.qmd_absolutescore_max as points, coalesce(p.answers, 0) as answers, coalesce(p.weights_found, 0) as weights_found,
  coalesce(p.real_partial, false) as real_partial,
  case when coalesce(p.weights_found, 0) = 0
       then 'proportional credit: no per-answer weights; check the switch carried over' end as scoring_note,
  p.weights, p.answers_text
from tests t
join questions q     on q.col_pk = t.col_pk
join qti_asi_data qq on qq.pk1 = q.question_pk
join qx              on qx.question_pk = q.question_pk
left join per_q p    on p.question_pk = q.question_pk
order by t.course_id, real_partial desc, t.test_title, qq.position;


-- S5d. Question types in every test, including questions drawn through random blocks and question
--      sets. Ultra removes four types on conversion: File Response (File Upload, code 10), Opinion
--      Scale/Likert (15), Ordering (4) and Quiz Bowl (14), per Blackboard's help (Course Preview,
--      "Unsupported question types", read 2026-11-14). Codes mapped from the question XML on demo.
with scope as ({SCOPE}),
tests as (
  select s.course_id, gm.pk1 as col_pk, gm.title as test_title, gm.qti_asi_data_pk1 as asmt_pk
  from scope s
  join gradebook_main gm on gm.crsmain_pk1 = s.crs_pk and gm.qti_asi_data_pk1 is not null
                        and coalesce(gm.deleted_ind, 'N') = 'N'),
questions as (
  select t.col_pk, q.pk1 as question_pk
  from tests t
  join qti_asi_data sec on sec.parent_pk1 = t.asmt_pk
  join qti_asi_data q   on q.parent_pk1 = sec.pk1 and q.bbmd_asi_type = 3
  union
  select t.col_pk, pq.pk1
  from tests t
  join qti_asi_data sec on sec.parent_pk1 = t.asmt_pk
  join qti_asi_data blk on blk.parent_pk1 = sec.pk1
  join qti_block_mapping m on m.question_block_pk1 = blk.pk1
  join qti_asi_data pq  on pq.pk1 = m.question_pk1)
select t.course_id, t.test_title, q.bbmd_questiontype as question_type_code,
  case q.bbmd_questiontype
    when 1 then 'Multiple Choice' when 2 then 'True/False' when 3 then 'Multiple Answer'
    when 4 then 'Ordering' when 5 then 'Matching' when 6 then 'Fill in the Blank' when 7 then 'Essay'
    when 8 then 'Numeric' when 9 then 'Calculated' when 10 then 'File Upload' when 11 then 'Hot Spot'
    when 12 then 'Fill in the Blank Plus' when 13 then 'Jumbled Sentence' when 14 then 'Quiz Bowl'
    when 15 then 'Opinion Scale' when 16 then 'Short Response' when 17 then 'Either/Or'
    when 19 then 'Presentation Only' when 20 then 'Page Break' when 21 then 'AI Chat'
    else 'code ' || q.bbmd_questiontype end                    as question_type,
  q.bbmd_questiontype in (4, 10, 14, 15)                       as removed_by_conversion,
  count(distinct q.pk1)                                        as questions
from tests t
join questions qq    on qq.col_pk = t.col_pk
join qti_asi_data q  on q.pk1 = qq.question_pk
group by t.course_id, t.test_title, q.bbmd_questiontype
order by t.course_id, t.test_title, q.bbmd_questiontype;

-- S5e. Question sources per course: tests, pools and question banks, and how many questions tests
--      draw through random blocks and question sets. With the site setting that turns undeployed
--      tests into question banks (S14), those tests lose their random blocks and question sets, so
--      the post-scan checks the draws are all still there.
with scope as ({SCOPE}),
a as (
  select s.course_id, x.pk1 as asmt_pk, x.bbmd_assessmenttype as atype
  from scope s
  join qti_asi_data x on x.crsmain_pk1 = s.crs_pk and x.bbmd_asi_type = 1),
draws as (
  select a.course_id, count(*) as n
  from a
  join qti_asi_data sec on sec.parent_pk1 = a.asmt_pk
  join qti_asi_data blk on blk.parent_pk1 = sec.pk1
  join qti_block_mapping m on m.question_block_pk1 = blk.pk1
  group by a.course_id)
select a.course_id,
  count(*) filter (where a.atype = 1)                as tests,
  count(*) filter (where a.atype = 4)                as pools_and_banks,
  count(*) filter (where a.atype not in (1, 4))      as other_assessments,
  coalesce(max(d.n), 0)                              as block_draws
from a
left join draws d on d.course_id = a.course_id
group by a.course_id
order by a.course_id;

-- S5f. Undeployed tests (a test with no course_assessment row: never added to the course), with
--      how many other tests draw questions from each through random blocks and question sets.
--      With the site setting that turns undeployed tests into question banks on (S14), Blackboard's
--      help says the banks lose random blocks, question sets and linked questions, so the tests
--      that draw from them may come up short. On demo 2026-11-15: 343 undeployed tests in Original
--      courses, 4 of them drawn from. One row per undeployed test.
with scope as ({SCOPE}),
setting as (
  select max(r.registry_value) as v
  from system_registry r
  where r.registry_key = 'ultraui.converting.undeployed.tests.to.question.banks'),
undeployed as (
  select s.course_id, x.pk1 as asmt_pk, x.title
  from scope s
  join qti_asi_data x on x.crsmain_pk1 = s.crs_pk and x.bbmd_asi_type = 1 and x.bbmd_assessmenttype = 1
  where not exists (select 1 from course_assessment ca where ca.qti_asi_data_pk1 = x.pk1)),
uq as (
  select u.asmt_pk, q.pk1 as question_pk
  from undeployed u
  join qti_asi_data sec on sec.parent_pk1 = u.asmt_pk
  join qti_asi_data q   on q.parent_pk1 = sec.pk1 and q.bbmd_asi_type = 3),
drawn as (
  select uq.asmt_pk, count(*) as draws, count(distinct dt.pk1) as drawing_tests,
         string_agg(distinct dt.title, '; ') as drawing_test_titles
  from uq
  join qti_block_mapping m on m.question_pk1 = uq.question_pk
  join qti_asi_data blk    on blk.pk1 = m.question_block_pk1
  join qti_asi_data sec    on sec.pk1 = blk.parent_pk1
  join qti_asi_data dt     on dt.pk1 = sec.parent_pk1 and dt.pk1 <> uq.asmt_pk
  group by uq.asmt_pk)
select u.course_id, u.asmt_pk, u.title as test_title,
  (select count(*) from uq where uq.asmt_pk = u.asmt_pk) as questions,
  coalesce(d.drawing_tests, 0) as drawing_tests, coalesce(d.draws, 0) as draws, d.drawing_test_titles,
  st.v as bank_setting, coalesce(st.v = 'true', false) as becomes_bank
from undeployed u
cross join setting st
left join drawn d on d.asmt_pk = u.asmt_pk
order by u.course_id, u.title;


-- ===========================================================================
-- S6. SCORM settings per package: attempts allowed, grade timing, player time limit,
--     and how many engine package versions sit behind the item.
-- ===========================================================================
with scope as ({SCOPE})
select s.course_id, cc.pk1 as content_pk, cc.title,
  pi.max_attempts, pi.gradebook_score_timing,
  count(distinct p.scorm_package_id)                                   as engine_package_versions,
  max(pp.time_limit)                                                   as player_time_limit,
  string_agg(distinct gi.gradebook_column_id, ', ')                    as grade_column_ids
from scope s
join course_contents cc on cc.crsmain_pk1 = s.crs_pk and cc.cnthndlr_handle = 'resource/x-plugin-scormengine'
left join scormbbpackageinfo pi     on pi.content_id = '_' || cc.pk1 || '_1'
left join scormbbgradebookinfo gi   on gi.content_id = '_' || cc.pk1 || '_1'
left join scormpackage p            on p.api_course_id = '_' || cc.pk1 || '_1'
left join scormpackageproperties pp on pp.scorm_package_id = p.scorm_package_id
group by s.course_id, cc.pk1, cc.title, pi.max_attempts, pi.gradebook_score_timing
order by s.course_id, cc.pk1;


-- ===========================================================================
-- S7. Per-learner baseline: one row per student per gradable column (the core of the compare).
--     Deleted and calculated columns are excluded. The learner filter (the LEARNERS placeholder,
--     filled in by convscan) narrows the students: by default
--     to those available (in progress), with the rest totalled in S2b; empty for every enabled
--     student (--all-learners); on a post-scan, the learners its baseline read.
--     The grade rows are picked first, so attempts are counted only for the learners read.
--     Attempts are counted per grade row through a lateral index lookup, not a join to an
--     aggregate: on a reporting replica with stale statistics the planner can expect one row
--     where there are hundreds of thousands, and a nested-loop join to the aggregate then
--     rescans it for every grade row (a large course went from a timeout to about 20 s).
-- ===========================================================================
with scope as ({SCOPE}),
gr as (
  select s.course_id, cu.users_pk1, cu.pk1 as cu_pk, cu.available_ind as learner_available,
         gm.pk1 as col_pk, gm.title as column_title, gm.course_contents_pk1 as content_pk,
         gm.score_provider_handle, gg.pk1 as gg_pk, gg.status as grade_status, gg.manual_score,
         gg.exempt_ind, gg.last_attempt_pk1, gg.highest_attempt_pk1, gg.last_attempt_date
  from scope s
  join course_users cu    on cu.crsmain_pk1 = s.crs_pk and cu.role = 'S' and cu.row_status = 0 {LEARNERS}
  join gradebook_main gm  on gm.crsmain_pk1 = s.crs_pk and coalesce(gm.calculated_ind, 'N') = 'N'
                         and coalesce(gm.deleted_ind, 'N') = 'N'
  join gradebook_grade gg on gg.gradebook_main_pk1 = gm.pk1 and gg.course_users_pk1 = cu.pk1)
select gr.course_id, gr.users_pk1, gr.cu_pk, gr.learner_available,
  gr.col_pk, gr.column_title, gr.content_pk, gr.score_provider_handle,
  gr.grade_status, gr.manual_score, gr.exempt_ind,
  la.score as last_attempt_score, ha.score as highest_attempt_score,
  coalesce(att.attempts, 0) as attempts, coalesce(att.submitted, 0) as submitted,
  coalesce(att.open, 0) as open, coalesce(att.needs_grading, 0) as needs_grading,
  gr.last_attempt_date
from gr
left join lateral (
  select count(*)                                    as attempts,
         count(*) filter (where a.status in (6, 7, 9)) as submitted,
         count(*) filter (where a.status in (3, 4, 8)) as open,
         count(*) filter (where a.status in (6, 9))    as needs_grading
  from attempt a
  where a.gradebook_grade_pk1 = gr.gg_pk) att on true
left join attempt la on la.pk1 = gr.last_attempt_pk1
left join attempt ha on ha.pk1 = coalesce(gr.highest_attempt_pk1, gr.last_attempt_pk1)
order by gr.course_id, gr.users_pk1, gr.col_pk;

-- ===========================================================================
-- S8. Groups, members, and what uses each group: release criteria and test exceptions
--     (counted once per table for the whole scope, not group by group)
-- ===========================================================================
with scope as ({SCOPE}),
grp as (
  select s.course_id, g.pk1, g.group_name
  from scope s
  join groups g on g.crsmain_pk1 = s.crs_pk),
mem as (
  select gu.groups_pk1, count(*) as n
  from grp join group_users gu on gu.groups_pk1 = grp.pk1
  group by gu.groups_pk1),
crit as (
  select cg.groups_pk1, count(*) as n
  from grp join avl_crit_acl_group cg on cg.groups_pk1 = grp.pk1
  group by cg.groups_pk1),
exc as (
  select o.groups_pk1, count(*) as n
  from grp join user_test_option o on o.groups_pk1 = grp.pk1
  group by o.groups_pk1)
select grp.course_id, grp.pk1 as group_pk, grp.group_name,
  coalesce(mem.n, 0)  as members,
  coalesce(crit.n, 0) as criteria_using_group,
  coalesce(exc.n, 0)  as test_exceptions_using_group
from grp
left join mem  on mem.groups_pk1 = grp.pk1
left join crit on crit.groups_pk1 = grp.pk1
left join exc  on exc.groups_pk1 = grp.pk1
order by grp.course_id, grp.group_name;

-- S8b. Per-learner group membership (users_pk1 and group name; names match across a copy).
--      Same learner filter as S7.
with scope as ({SCOPE})
select s.course_id, cu.users_pk1, g.group_name
from scope s
join groups g        on g.crsmain_pk1 = s.crs_pk
join group_users gu  on gu.groups_pk1 = g.pk1
join course_users cu on cu.pk1 = gu.course_users_pk1 and cu.row_status = 0 {LEARNERS}
order by s.course_id, g.group_name, cu.users_pk1;


-- ===========================================================================
-- S9. Release rules in full, with the groups and named users on each criterion
--     (compare by item title, parent title and rule title; Stage 1 Q2 plus names).
--     Criteria within a rule are AND; rules on the same item are OR.
-- ===========================================================================
with scope as ({SCOPE})
select s.course_id, cc.pk1 as content_pk, cc.title as item_title, p.title as parent_title,
  cc.cnthndlr_handle, ar.title as rule_title, ac.pk1 as crit_pk, ac.crit_type, ac.negate_ind,
  gm.title as gate_column_title, gm.calculated_ind as gate_column_calculated,
  ac.min_score, ac.max_score, ac.start_date, ac.end_date,
  rc.title as reviewed_item_title,                                       -- CONTENT_REVIEWED
  gn.groups_named, un.users_named, coalesce(un.users_named_count, 0) as users_named_count
from scope s
join course_contents cc on cc.crsmain_pk1 = s.crs_pk
left join course_contents p on p.pk1 = cc.parent_pk1
join avl_rule ar        on ar.course_contents_pk1 = cc.pk1
join avl_crit ac        on ac.avl_rule_pk1 = ar.pk1
left join gradebook_main gm on gm.pk1 = ac.gradebook_main_pk1
left join course_contents rc on rc.pk1 = ac.reviewed_content_pk1
left join lateral (
  select string_agg(g.group_name, ' | ' order by g.group_name) as groups_named
  from avl_crit_acl_group cg join groups g on g.pk1 = cg.groups_pk1
  where cg.avl_crit_pk1 = ac.pk1) gn on true
left join lateral (
  select string_agg(au.users_pk1::text, ' | ' order by au.users_pk1) as users_named,
         count(*) as users_named_count
  from avl_crit_acl_user au
  where au.avl_crit_pk1 = ac.pk1) un on true
order by s.course_id, cc.title, ar.title, ac.crit_type;


-- ===========================================================================
-- S10. Per-learner SCORM records, one row per learner per package per attempt, with a
--      fingerprint of the runtime state (bookmark, suspend data, status, score).
--      CONFIRMED on demo 2026-11-13: resume state IS in the database:
--      scormactivityrt.location and suspend_data per SCO, and
--      scormregistration.suspended_activity_id per registration.
--      Compare runtime_md5 between Original and copy: equal means the learner resumes in
--      the same place with the same state. A NULL runtime (scos is NULL) means the engine
--      has not yet written the state out of scormregistration.runtime_data, which was the
--      case for every record in the 2026-11-14 demo test. That blob is 4 bytes of length
--      plus a zlib-compressed RunTimeData XML document with the same fields per SCO
--      (Location, SuspendData, statuses, scores). It is returned raw here: convscan
--      decodes it while reading and writes only a fingerprint (blob_md5) and the bookmarks.
--      Run through another tool, drop the runtime_data column if it can't decode it.
--      Learners are matched by users_pk1 taken from api_registration_id
--      ('<content_id>-<user_id>'). Same learner filter as S7, applied in reg so that no other
--      learner's registration (or its runtime_data blob) is read.
--      Each registration's activities are read through a lateral lookup on the engine's indexes,
--      which all start with engine_tenant_id: joining on the registration and activity IDs alone
--      scans both activity tables in full for every scan (about 45 s on a large site, whatever
--      the scope; a 10-course batch went from 44 s to under 10 s).
-- ===========================================================================
with scope as ({SCOPE}),
pkg as (
  select s.course_id, s.crs_pk, cc.pk1 as content_pk, cc.title as scorm_title, p.scorm_package_id
  from scope s
  join course_contents cc on cc.crsmain_pk1 = s.crs_pk and cc.cnthndlr_handle = 'resource/x-plugin-scormengine'
  join scormpackage p     on p.api_course_id = '_' || cc.pk1 || '_1'),
reg as (
  select pkg.course_id, pkg.content_pk, pkg.scorm_title, cu.users_pk1, cu.available_ind,
         r.engine_tenant_id, r.scorm_registration_id, r.instance_id, r.completed_dt_utc,
         r.suspended_activity_id, r.runtime_data
  from pkg
  join scormregistration r on r.scorm_package_id = pkg.scorm_package_id
  join course_users cu     on cu.crsmain_pk1 = pkg.crs_pk
                          and '_' || cu.users_pk1 || '_1' = split_part(r.api_registration_id, '-', 2)
                          and cu.role = 'S' and cu.row_status = 0 {LEARNERS}),
rt as (
  -- A registration with no activity rows yet gets no rt row, so its scos stay NULL below.
  select reg.scorm_registration_id, x.scos, x.scos_with_location, x.scos_with_suspend, x.runtime_md5
  from reg
  cross join lateral (
    select count(*)                                                                     as scos,
           count(*) filter (where rt.location is not null and rt.location <> '')         as scos_with_location,
           count(*) filter (where rt.suspend_data is not null and rt.suspend_data <> '') as scos_with_suspend,
           md5(string_agg(coalesce(rt.location, '') || '|' || coalesce(rt.suspend_data, '')
                          || coalesce(rt.suspend_data_overflow, '') || '|' || coalesce(rt.completion_status::text, '')
                          || '|' || coalesce(rt.success_status::text, '') || '|' || coalesce(rt.score_raw::text, ''),
                          '#' order by a.scorm_activity_id))                            as runtime_md5
    from scormactivity a
    join scormactivityrt rt on rt.engine_tenant_id = a.engine_tenant_id and rt.scorm_activity_id = a.scorm_activity_id
    where a.engine_tenant_id = reg.engine_tenant_id
      and a.scorm_registration_id = reg.scorm_registration_id) x
  where x.scos > 0)
select reg.course_id, reg.users_pk1, reg.available_ind as learner_available, reg.content_pk, reg.scorm_title,
  reg.instance_id + 1                      as attempt_no,
  reg.completed_dt_utc,
  reg.suspended_activity_id is not null    as suspended,
  rt.scos, rt.scos_with_location, rt.scos_with_suspend, rt.runtime_md5,
  reg.runtime_data           -- convscan decodes this and keeps only a fingerprint (blob_md5)
from reg
left join rt on rt.scorm_registration_id = reg.scorm_registration_id
order by reg.course_id, reg.users_pk1, reg.content_pk, reg.instance_id;


-- ===========================================================================
-- S11. Discussion volume (all posts, not only in progress; copied with activity)
-- ===========================================================================
with scope as ({SCOPE})
select s.course_id, count(distinct fm.pk1) as forums, count(mm.pk1) as posts,
  count(distinct mm.users_pk1) as posting_users
from scope s
join conference_main conf on conf.crsmain_pk1 = s.crs_pk
join forum_main fm on fm.confmain_pk1 = conf.pk1
left join msg_main mm on mm.forummain_pk1 = fm.pk1
group by s.course_id
order by posts desc;


-- ===========================================================================
-- S12. Test settings that matter at freeze and at conversion: time limit (minutes),
--      auto-submit, attempts allowed, password, proctoring and LockDown Browser, and the
--      open attempts on each test (tier 1 at cutover: a timed attempt left open during
--      the freeze may auto-submit or expire). Proctoring and secure-browser settings
--      need checking in the Ultra copy.
-- ===========================================================================
with scope as ({SCOPE}),
open_att as (
  select gg.gradebook_main_pk1 as col_pk,
         count(a.pk1)                       as open_attempts,
         count(distinct gg.course_users_pk1) as learners_with_open_attempt,
         max(a.attempt_date)                as latest_open_attempt
  from scope s
  join gradebook_main gm  on gm.crsmain_pk1 = s.crs_pk
  join gradebook_grade gg on gg.gradebook_main_pk1 = gm.pk1
  join attempt a          on a.gradebook_grade_pk1 = gg.pk1 and a.status in (3, 4, 8)
  group by gg.gradebook_main_pk1)
select s.course_id, gm.pk1 as col_pk, gm.title as test_title,
  ca.time_limit as time_limit_minutes, ca.soft_time_limit, ca.timer_completion,
  case ca.timer_completion when 'H' then 'ON' when 'C' then 'OFF' end as auto_submit, ca.force_completion_ind,
  ca.multiple_attempts_ind, ca.unlimited_attempts_ind, ca.attempt_count,
  ca.password_ind, ca.proctoring_service_handle, ca.req_secure_browser_take_ind,
  (select count(*) from user_test_option o where o.course_assessment_pk1 = ca.pk1) as exceptions,
  coalesce(oa.open_attempts, 0) as open_attempts,
  coalesce(oa.learners_with_open_attempt, 0) as learners_with_open_attempt,
  oa.latest_open_attempt
from scope s
join gradebook_main gm    on gm.crsmain_pk1 = s.crs_pk and gm.qti_asi_data_pk1 is not null
                         and coalesce(gm.deleted_ind, 'N') = 'N'
join course_assessment ca on ca.qti_asi_data_pk1 = gm.qti_asi_data_pk1
left join open_att oa     on oa.col_pk = gm.pk1
order by s.course_id, open_attempts desc, gm.title;

-- S12b. Test exceptions (Original "test availability exceptions"): per learner or per group,
--       with the time limit and attempts they change. A second place accommodations live
--       (alongside group release rules). Whether conversion keeps them, and whether a
--       group-based exception survives the loss of groups, is NOT yet tested.
with scope as ({SCOPE})
select s.course_id, gm.pk1 as col_pk, gm.title as test_title,
  case when o.groups_pk1 is not null then 'group' else 'learner' end as applies_to,
  cu.users_pk1, g.group_name,
  o.time_limit as time_limit_minutes, o.timer_completion, o.force_completion_ind,
  o.multiple_attempts_ind, o.unlimited_attempts_ind, o.attempt_count,
  ca.time_limit as test_time_limit_minutes
from scope s
join course_assessment ca on ca.crsmain_pk1 = s.crs_pk
join user_test_option o   on o.course_assessment_pk1 = ca.pk1
left join gradebook_main gm on gm.qti_asi_data_pk1 = ca.qti_asi_data_pk1 and coalesce(gm.deleted_ind, 'N') = 'N'
left join course_users cu on cu.pk1 = o.course_users_pk1
left join groups g        on g.pk1 = o.groups_pk1
order by s.course_id, gm.title, applies_to, g.group_name, cu.users_pk1;


-- ===========================================================================
-- S13. System tasks for each course (queued_tasks): restore, copy and convert, and the
--      follow-on tasks a copy triggers (for example assessment file migration).
--      Matched by the task's course, or by the course IDs in a copy task's title
--      ('copy|course.copy.queue.task.label|<new course_id>,<source course_id>').
--      status (seen on demo 2026-11-14): C complete, E error, I in progress. task_type for
--      the bulk copy and convert is BulkCopyAndConvertOperation, and results holds the
--      outcome message, including warnings (for example a missing LTI placement on restore).
--      Three equality joins combined with union (not one OR join), so each can be hashed.
-- ===========================================================================
with scope as ({SCOPE}),
copy_tasks as (
  select qt.pk1, regexp_replace(qt.title, '^[^|]*\|[^|]*\|', '') as subject
  from queued_tasks qt
  where qt.title like 'copy|%'),
ids as (
  select s.course_id, qt.pk1
  from scope s join queued_tasks qt on qt.course_main_pk1 = s.crs_pk
  union
  select s.course_id, c.pk1
  from scope s join copy_tasks c on s.course_id = split_part(c.subject, ',', 1)
  union
  select s.course_id, c.pk1
  from scope s join copy_tasks c on s.course_id = split_part(c.subject, ',', 2))
select ids.course_id, t.pk1 as task_pk, t.task_type, t.status,
  case t.status when 'C' then 'complete' when 'E' then 'error' when 'I' then 'in progress' else t.status end as status_label,
  t.dtcreated, t.start_date, t.end_date,
  extract(epoch from (t.end_date - t.start_date))::int as seconds,
  t.progress, regexp_replace(t.title, '^[^|]*\|[^|]*\|', '') as task_subject, left(t.results, 400) as results_text
from ids
join queued_tasks t on t.pk1 = ids.pk1
order by ids.course_id, t.dtcreated;


-- ===========================================================================
-- S14. Site conversion settings (system_registry), recorded with every run because they shape
--      what a conversion produces (Admin > Ultra Experience Management). Keys seen on demo
--      2026-11-14: nesting levels (3 by default, 4 with the additional level, which can't be
--      undone), content areas to learning modules, folder and learning module descriptions to
--      documents, and undeployed tests to question banks. Not scoped to courses.
--      Also the LMS version (release_number, for example 4001.7.0-rel.4+a1cda0a), so every
--      report says which version it ran on, and the release-condition inheritance feature flag
--      (stored as JSON; on in 4001.7 on demo), which decides whether content takes the release
--      conditions of the folder or learning module it sits in.
-- ===========================================================================
select r.registry_key, r.registry_value
from system_registry r
where r.registry_key in ('release_number',
                         'featureFlags:feature.course.release.condition.inheritance:Tenant',
                         'course.structure.max_level_of_nesting',
                         'ultraui.converting.content.areas.to.learning.modules',
                         'ultraui.converting.folder.and.learning.module.descriptions.to.documents',
                         'ultraui.converting.undeployed.tests.to.question.banks')
order by r.registry_key;


-- ===========================================================================
-- M1. (No SQL.) Item match, Original to copy: from S3b on both scopes, match on
--     (handler, title, parent title), then (handler, title). Conversion adds wrapper
--     folders and can duplicate a folder's rules, so one Original item may match two
--     copy items; flag rather than drop.
-- ===========================================================================


-- ===========================================================================
-- M2. Column map, Original to copy, matched by attached item, not by name
--     (replaces Stage 1 Q9, which matched on title). One row per Original column.
--     Feeds the ID map in the hand-off report.
--     Normalized before matching (all seen on demo 2026-11-14, comparing real conversions):
--       * titles: conversion strips HTML from item titles ('<u>Chapter 1</u>' becomes
--         'Chapter 1') and plain-texts typography (en and em dashes to hyphens, curly
--         quotes to straight), so tags, typography, case and repeated spaces are ignored,
--       * type: an Original assignment (resource/x-bb-assignment) becomes an Ultra
--         assessment (resource/x-bb-assessment), so the two count as the same type,
--       * calculated: Original's T, W, M and so on all become C in Ultra, so only
--         calculated or not is compared. Ultra drops the Weighted Total column.
-- ===========================================================================
with pairs as ({PAIRS}),                                -- orig_course_id, new_course_id
o as (
  select p.orig_course_id, p.new_course_id, gm.pk1 as col_pk, gm.title, gm.score_provider_handle,
         gm.calculated_ind, gm.visible_ind, gm.visible_in_book_ind, cc.title as content_title, cc.cnthndlr_handle,
         par.title as parent_title,
         lower(trim(translate(regexp_replace(regexp_replace(cc.title, '<[^>]*>', '', 'g'), '\s+', ' ', 'g'), '–—‘’“”', '--''''""')))  as c_norm,
         lower(trim(translate(regexp_replace(regexp_replace(par.title, '<[^>]*>', '', 'g'), '\s+', ' ', 'g'), '–—‘’“”', '--''''""'))) as p_norm,
         lower(trim(translate(regexp_replace(regexp_replace(gm.title, '<[^>]*>', '', 'g'), '\s+', ' ', 'g'), '–—‘’“”', '--''''""')))  as t_norm,
         replace(coalesce(gm.score_provider_handle, ''), 'resource/x-bb-assignment', 'resource/x-bb-assessment') as h_norm,
         coalesce(gm.calculated_ind, 'N') <> 'N' as is_calc
  from pairs p
  join course_main cm on cm.course_id = p.orig_course_id
  join gradebook_main gm on gm.crsmain_pk1 = cm.pk1 and coalesce(gm.deleted_ind, 'N') = 'N'
  left join course_contents cc  on cc.pk1 = gm.course_contents_pk1
  left join course_contents par on par.pk1 = cc.parent_pk1),
n as (
  select p.new_course_id, gm.pk1 as col_pk, gm.title, gm.score_provider_handle, gm.calculated_ind,
         gm.visible_ind, gm.visible_in_book_ind, cc.title as content_title, cc.cnthndlr_handle, par.title as parent_title,
         lower(trim(translate(regexp_replace(regexp_replace(cc.title, '<[^>]*>', '', 'g'), '\s+', ' ', 'g'), '–—‘’“”', '--''''""')))  as c_norm,
         lower(trim(translate(regexp_replace(regexp_replace(par.title, '<[^>]*>', '', 'g'), '\s+', ' ', 'g'), '–—‘’“”', '--''''""'))) as p_norm,
         lower(trim(translate(regexp_replace(regexp_replace(gm.title, '<[^>]*>', '', 'g'), '\s+', ' ', 'g'), '–—‘’“”', '--''''""')))  as t_norm,
         replace(coalesce(gm.score_provider_handle, ''), 'resource/x-bb-assignment', 'resource/x-bb-assessment') as h_norm,
         coalesce(gm.calculated_ind, 'N') <> 'N' as is_calc
  from pairs p
  join course_main cm on cm.course_id = p.new_course_id
  join gradebook_main gm on gm.crsmain_pk1 = cm.pk1 and coalesce(gm.deleted_ind, 'N') = 'N'
  left join course_contents cc  on cc.pk1 = gm.course_contents_pk1
  left join course_contents par on par.pk1 = cc.parent_pk1),
cand as (
  select o.*, n.col_pk as new_col_pk, n.visible_ind as new_visible_ind, n.visible_in_book_ind as new_in_book_ind,
    case
      when o.c_norm is not null and n.c_norm = o.c_norm and n.h_norm = o.h_norm
           and n.p_norm is not distinct from o.p_norm                 then 1  -- item, type, parent
      when o.c_norm is not null and n.c_norm = o.c_norm and n.h_norm = o.h_norm then 2  -- item and type
      when o.c_norm is null and n.c_norm is null                              -- unattached to unattached:
           and n.t_norm = o.t_norm and n.is_calc = o.is_calc then 3              -- title
    end as match_level
  from o join n on n.new_course_id = o.new_course_id),
best as (                                  -- each Original column's candidates at its best level
  select c.*,
         (c.new_visible_ind is not distinct from c.visible_ind
          and c.new_in_book_ind is not distinct from c.visible_in_book_ind) as same_vis
  from (select c.*, min(match_level) over (partition by c.col_pk) as best_level
        from cand c where match_level is not null) c
  where c.match_level = c.best_level),
vis as (                                   -- tie-break 1: keep candidates with the same visibility
  select b.*, bool_or(b.same_vis) over (partition by b.col_pk) as any_same_vis  -- (to learners and
  from best b),                                                                 --  in the Grade Center)
grp as (
  select v.col_pk, v.new_course_id, v.best_level,
         count(*)                                                        as n_all,
         count(*) filter (where v.same_vis or not v.any_same_vis)        as n_cand,
         string_agg(v.new_col_pk::text, ',' order by v.new_col_pk)
           filter (where v.same_vis or not v.any_same_vis)               as cand_set,
         string_agg(v.new_col_pk::text, ', ' order by v.new_col_pk)      as candidates
  from vis v group by v.col_pk, v.new_course_id, v.best_level),
ranked as (                                -- tie-break 2: Original columns that share the same
  select g.*,                              -- candidate set pair off in creation order (pk), since
         row_number() over (partition by g.new_course_id, g.cand_set order by g.col_pk) as o_rank,
         count(*) over (partition by g.new_course_id, g.cand_set)                     as n_orig
  from grp g)                              -- the copy keeps the columns in the same order
select o.orig_course_id, o.new_course_id, o.col_pk as orig_col_pk, o.title, o.content_title,
  o.score_provider_handle, o.calculated_ind, o.visible_ind,
  case when r.col_pk is null              then 'not found'
       when r.n_all = 1                   then 'matched'
       when r.n_cand = 1                  then 'matched (visibility tie-break)'
       when r.n_cand = r.n_orig           then 'matched (order tie-break)'
       else 'ambiguous' end                                                   as match_status,
  case when r.n_cand = 1                  then split_part(r.cand_set, ',', 1)::bigint
       when r.n_cand = r.n_orig           then split_part(r.cand_set, ',', r.o_rank::int)::bigint
  end                                                                         as new_col_pk,  -- blank when ambiguous
  r.best_level                                                                as match_level,
  r.candidates
from o
left join ranked r on r.col_pk = o.col_pk
order by o.orig_course_id, o.col_pk;
