# coding: utf-8
#
# Copyright 2014 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = 'Stephanie Federwisch'

"""Tests for statistics continuous computations."""

from core import jobs_registry
from core.domain import event_services
from core.domain import exp_domain
from core.domain import exp_services
from core.domain import stats_jobs
from core.platform import models
(stats_models, exp_models) = models.Registry.import_models([models.NAMES.statistics, models.NAMES.exploration])
from core.tests import test_utils
import feconf
from datetime import datetime


class ModifiedStatisticsAggregator(stats_jobs.StatisticsAggregator):
    """A modified StatisticsAggregator that does not start a new batch
    job when the previous one has finished.
    """
    @classmethod
    def _get_batch_job_manager_class(cls):
        return ModifiedStatisticsMRJobManager

    @classmethod
    def _kickoff_batch_job_after_previous_one_ends(cls):
        pass


class ModifiedStatisticsMRJobManager(stats_jobs.StatisticsMRJobManager):

    @classmethod
    def _get_continuous_computation_class(cls):
        return ModifiedStatisticsAggregator


class OneOffFixStartCounts(test_utils.GenericTestBase):
    def test_job(self):
        exp_id = 'eid'
        exploration = self.save_new_valid_exploration(exp_id, 'owner')
        first_init_state = 'first state name'
        exploration.rename_state(exploration.init_state_name, first_init_state)
        exp_services._save_exploration('person', exploration, 'message', None)
        metadata = exp_models.ExplorationSnapshotMetadataModel.get('%s-%s' % (
            exp_id, 2))
        metadata.created_on = datetime(2014, 10, 3)
        metadata.put()

        first_state_counter = (
            stats_models.StateCounterModel.get_or_create(exp_id, first_init_state))
        first_state_counter.first_entry_count = 17
        first_state_counter.put()

        for _ in range(17):
            entity_id = stats_models.StartExplorationEventLogEntryModel.create(
                exp_id, 2, first_init_state, 'session_id', {}, feconf.PLAY_TYPE_NORMAL)
            entity = stats_models.StartExplorationEventLogEntryModel.get(entity_id)
            entity.created_on = datetime(2014, 10, 5)
            entity.put()

        second_init_state = 'second init state'
        exploration.rename_state(first_init_state, second_init_state)
        exp_services._save_exploration('person', exploration, 'message', None)
        metadata = exp_models.ExplorationSnapshotMetadataModel.get('%s-%s' % (
            exp_id, 3))
        metadata.created_on = datetime(2014, 10, 6)
        metadata.put()

        for _ in range(13):
            entity_id = stats_models.StartExplorationEventLogEntryModel.create(
                exp_id, 3, second_init_state, 'session_id', {}, feconf.PLAY_TYPE_NORMAL)
            entity = stats_models.StartExplorationEventLogEntryModel.get(entity_id)
            entity.created_on = datetime(2014, 10, 7)
            entity.put()
        
        second_state_counter = (
            stats_models.StateCounterModel.get_or_create(exp_id, second_init_state))
        second_state_counter.first_entry_count = -17
        second_state_counter.put()

        for _ in range(19):
            entity_id = stats_models.StartExplorationEventLogEntryModel.create(
                exp_id, 1, second_init_state, 'session_id', {}, feconf.PLAY_TYPE_NORMAL)
            entity = stats_models.StartExplorationEventLogEntryModel.get(entity_id)
            entity.created_on = datetime(2014, 10, 19)
            entity.put()

        job_id = stats_jobs.OneOffFixStartCounts.create_new()
        stats_jobs.OneOffFixStartCounts.enqueue(job_id)
        self.process_and_flush_pending_tasks()

        first_state_counter = (
            stats_models.StateCounterModel.get_or_create(exp_id, first_init_state))
        self.assertEqual(first_state_counter.first_entry_count, 0)
        second_state_counter = (
            stats_models.StateCounterModel.get_or_create(exp_id, second_init_state))
        self.assertEqual(second_state_counter.first_entry_count, 0)

        job_id = stats_jobs.OneOffFixStartCounts.create_new()
        stats_jobs.OneOffFixStartCounts.enqueue(job_id)
        self.process_and_flush_pending_tasks()

        first_state_counter = (
            stats_models.StateCounterModel.get_or_create(exp_id, first_init_state))
        self.assertEqual(first_state_counter.first_entry_count, 0)
        second_state_counter = (
            stats_models.StateCounterModel.get_or_create(exp_id, second_init_state))
        self.assertEqual(second_state_counter.first_entry_count, 0)



class StatsAggregatorUnitTests(test_utils.GenericTestBase):
    """Tests for statistics aggregations."""

    ALL_CONTINUOUS_COMPUTATION_MANAGERS_FOR_TESTS = [
        ModifiedStatisticsAggregator]

    def _record_start(self, exp_id, exp_version, state, session_id):
        event_services.StartExplorationEventHandler.record(
            exp_id, exp_version, state, session_id, {},
            feconf.PLAY_TYPE_NORMAL)

    def _record_leave(self, exp_id, exp_version, state, session_id):
        event_services.MaybeLeaveExplorationEventHandler.record(
            exp_id, exp_version, state, session_id, 27, {},
            feconf.PLAY_TYPE_NORMAL)

    def _record_state_hit(self, exp_id, exp_version, state, session_id):
        event_services.StateHitEventHandler.record(
            exp_id, exp_version, state, session_id, {},
            feconf.PLAY_TYPE_NORMAL)

    def _create_state_counter(self, exp_id, state, first_entry_count):
        counter = stats_models.StateCounterModel.get_or_create(exp_id, state)
        counter.first_entry_count = first_entry_count
        counter.put()

    def test_state_hit(self):
        with self.swap(
                jobs_registry, 'ALL_CONTINUOUS_COMPUTATION_MANAGERS',
                self.ALL_CONTINUOUS_COMPUTATION_MANAGERS_FOR_TESTS):
            exp_id = 'eid'
            exp_version = 1
            exploration = self.save_new_valid_exploration(exp_id, 'owner')
            state = exploration.init_state_name
            state2 = 'sid2'

            self._record_state_hit(exp_id, exp_version, state, 'session1')
            self._record_state_hit(exp_id, exp_version, state, 'session2')
            self._create_state_counter(exp_id, state, 18)
            self._record_state_hit(exp_id, exp_version, state2, 'session1')
            self._create_state_counter(exp_id, state2, 9)
            self.process_and_flush_pending_tasks()

            ModifiedStatisticsAggregator.start_computation()
            self.assertEqual(self.count_jobs_in_taskqueue(), 1)
            self.process_and_flush_pending_tasks()

            output_model = stats_jobs.StatisticsAggregator.get_statistics(
                exp_id, exp_version)
            self.assertEqual(
                output_model['state_hit_counts'][state]['first_entry_count'],
                2)
            self.assertEqual(
                output_model['state_hit_counts'][state2]['first_entry_count'],
                1)

            output_model = stats_jobs.StatisticsAggregator.get_statistics(
                exp_id, stats_jobs._NO_SPECIFIED_VERSION_STRING)
            self.assertEqual(
                output_model['state_hit_counts'][state]['first_entry_count'],
                18)
            self.assertEqual(
                output_model['state_hit_counts'][state2]['first_entry_count'],
                9)

            output_model = stats_jobs.StatisticsAggregator.get_statistics(
                exp_id, stats_jobs._ALL_VERSIONS_STRING)
            self.assertEqual(
                output_model['state_hit_counts'][state]['first_entry_count'],
                20)
            self.assertEqual(
                output_model['state_hit_counts'][state2]['first_entry_count'],
                10)

    def test_no_completion(self):
        with self.swap(
                jobs_registry, 'ALL_CONTINUOUS_COMPUTATION_MANAGERS',
                self.ALL_CONTINUOUS_COMPUTATION_MANAGERS_FOR_TESTS):
            exp_id = 'eid'
            exp_version = 1
            exploration = self.save_new_valid_exploration(exp_id, 'owner')
            state = exploration.init_state_name

            self._record_start(exp_id, exp_version, state, 'session1')
            self._record_start(exp_id, exp_version, state, 'session2')
            self.process_and_flush_pending_tasks()

            ModifiedStatisticsAggregator.start_computation()
            self.assertEqual(self.count_jobs_in_taskqueue(), 1)
            self.process_and_flush_pending_tasks()

            model_id = '%s:%s' % (exp_id, exp_version)
            output_model = stats_models.ExplorationAnnotationsModel.get(
                model_id)
            self.assertEqual(output_model.num_starts, 2)
            self.assertEqual(output_model.num_completions, 0)

    def test_all_complete(self):
        with self.swap(
                jobs_registry, 'ALL_CONTINUOUS_COMPUTATION_MANAGERS',
                self.ALL_CONTINUOUS_COMPUTATION_MANAGERS_FOR_TESTS):
            exp_id = 'eid'
            exp_version = 1
            exploration = self.save_new_valid_exploration(exp_id, 'owner')
            state = exploration.init_state_name

            self._record_start(exp_id, exp_version, state, 'session1')
            self._record_leave(
                exp_id, exp_version, feconf.END_DEST, 'session1')
            self._record_start(exp_id, exp_version, state, 'session2')
            self._record_leave(
                exp_id, exp_version, feconf.END_DEST, 'session2')
            self.process_and_flush_pending_tasks()

            ModifiedStatisticsAggregator.start_computation()
            self.assertEqual(self.count_jobs_in_taskqueue(), 1)
            self.process_and_flush_pending_tasks()

            model_id = '%s:%s' % (exp_id, exp_version)
            output_model = stats_models.ExplorationAnnotationsModel.get(
                model_id)
            self.assertEqual(output_model.num_starts, 2)
            self.assertEqual(output_model.num_completions, 2)

    def test_multiple_maybe_leaves_same_session(self):
        with self.swap(
                jobs_registry, 'ALL_CONTINUOUS_COMPUTATION_MANAGERS',
                self.ALL_CONTINUOUS_COMPUTATION_MANAGERS_FOR_TESTS):
            exp_id = 'eid'
            exp_version = 1
            exploration = self.save_new_valid_exploration(exp_id, 'owner')
            state = exploration.init_state_name

            self._record_start(exp_id, exp_version, state, 'session1')
            self._record_leave(exp_id, exp_version, state, 'session1')
            self._record_leave(exp_id, exp_version, state, 'session1')
            self._record_leave(
                exp_id, exp_version, feconf.END_DEST, 'session1')

            self._record_start(exp_id, exp_version, state, 'session2')
            self._record_leave(exp_id, exp_version, state, 'session2')
            self._record_leave(exp_id, exp_version, state, 'session2')
            self.process_and_flush_pending_tasks()

            ModifiedStatisticsAggregator.start_computation()
            self.assertEqual(self.count_jobs_in_taskqueue(), 1)
            self.process_and_flush_pending_tasks()

            model_id = '%s:%s' % (exp_id, exp_version)
            output_model = stats_models.ExplorationAnnotationsModel.get(
                model_id)
            self.assertEqual(output_model.num_starts, 2)
            self.assertEqual(output_model.num_completions, 1)

    def test_multiple_explorations(self):
        with self.swap(
                jobs_registry, 'ALL_CONTINUOUS_COMPUTATION_MANAGERS',
                self.ALL_CONTINUOUS_COMPUTATION_MANAGERS_FOR_TESTS):

            exp_version = 1
            exp_id_1 = 'eid1'
            exploration = self.save_new_valid_exploration(exp_id_1, 'owner')
            state_1_1 = exploration.init_state_name
            exp_id_2 = 'eid2'
            exploration = self.save_new_valid_exploration(exp_id_2, 'owner')
            state_2_1 = exploration.init_state_name

            EMPTY_STATE_HIT_COUNTS_DICT = {
                'First State': {
                    'total_entry_count': 0,
                    'no_answer_count': 0,
                    'first_entry_count': 0,
                },
            }

            # Record 2 start events for exp_id_1 and 1 start event for
            # exp_id_2.
            self._record_start(exp_id_1, exp_version, state_1_1, 'session1')
            self._record_start(exp_id_1, exp_version, state_1_1, 'session2')
            self._record_start(exp_id_2, exp_version, state_2_1, 'session3')
            self.process_and_flush_pending_tasks()
            ModifiedStatisticsAggregator.start_computation()
            self.assertEqual(self.count_jobs_in_taskqueue(), 1)
            self.process_and_flush_pending_tasks()
            results = ModifiedStatisticsAggregator.get_statistics(
                exp_id_1, 'all')
            self.assertDictContainsSubset({
                'start_exploration_count': 2,
                'complete_exploration_count': 0,
                'state_hit_counts': EMPTY_STATE_HIT_COUNTS_DICT,
            }, results)
            results = ModifiedStatisticsAggregator.get_statistics(
                exp_id_2, 'all')
            self.assertDictContainsSubset({
                'start_exploration_count': 1,
                'complete_exploration_count': 0,
                'state_hit_counts': EMPTY_STATE_HIT_COUNTS_DICT,
            }, results)

            # Record 1 more start event for exp_id_1 and 1 more start event
            # for exp_id_2.
            self._record_start(exp_id_1, exp_version, state_1_1, 'session2')
            self._record_start(exp_id_2, exp_version, state_2_1, 'session3')
            self.process_and_flush_pending_tasks()
            results = ModifiedStatisticsAggregator.get_statistics(
                exp_id_1, 'all')
            self.assertDictContainsSubset({
                'start_exploration_count': 3,
                'complete_exploration_count': 0,
                'state_hit_counts': EMPTY_STATE_HIT_COUNTS_DICT,
            }, results)
            results = ModifiedStatisticsAggregator.get_statistics(
                exp_id_2, 'all')
            self.assertDictContainsSubset({
                'start_exploration_count': 2,
                'complete_exploration_count': 0,
                'state_hit_counts': EMPTY_STATE_HIT_COUNTS_DICT,
            }, results)


class OneOffNullStateHitEventsMigratorTest(test_utils.GenericTestBase):

    EXP_ID = 'exp_id'

    def setUp(self):
        super(OneOffNullStateHitEventsMigratorTest, self).setUp()

        self.save_new_valid_exploration(
            self.EXP_ID, 'user_id', 'title', 'category')
        exploration = exp_services.get_exploration_by_id(self.EXP_ID)

        # Create one good and two bad StateHit events.
        event_services.StateHitEventHandler.record(
            self.EXP_ID, 1, exploration.init_state_name,
            'good_session_id', {}, feconf.PLAY_TYPE_NORMAL)
        event_services.StateHitEventHandler.record(
            self.EXP_ID, 1, None,
            'bad_session_id_1', {'a': 'b'}, feconf.PLAY_TYPE_NORMAL)
        event_services.StateHitEventHandler.record(
            self.EXP_ID, 1, None,
            'bad_session_id_2', {}, feconf.PLAY_TYPE_NORMAL)
        self.process_and_flush_pending_tasks()

    def test_migration_job_works(self):
        self.assertEqual(
            stats_models.StateHitEventLogEntryModel.query().count(), 3)
        self.assertEqual(
            stats_models.MaybeLeaveExplorationEventLogEntryModel.query().count(),
            0)

        # Store a temporary copy of the instance corresponding to
        # bad_session_id_1.
        source_item = None
        for item in stats_models.StateHitEventLogEntryModel.query():
            if item.session_id == 'bad_session_id_1':
                source_item = item

        # Run the job once.
        job_id = (stats_jobs.NullStateHitEventsMigrator.create_new())
        stats_jobs.NullStateHitEventsMigrator.enqueue(job_id)
        self.assertEqual(self.count_jobs_in_taskqueue(), 1)

        self.process_and_flush_pending_tasks()

        self.assertEqual(
            stats_models.StateHitEventLogEntryModel.query().count(), 1)
        self.assertEqual(
            stats_models.MaybeLeaveExplorationEventLogEntryModel.query().count(),
            2)
        self.assertEqual(
            stats_jobs.NullStateHitEventsMigrator.get_output(job_id),
            [['migrated_instances', ['exp_id v1', 'exp_id v1']]])

        # Run the job again; nothing new should happen.
        new_job_id = (stats_jobs.NullStateHitEventsMigrator.create_new())
        stats_jobs.NullStateHitEventsMigrator.enqueue(new_job_id)
        self.assertEqual(self.count_jobs_in_taskqueue(), 1)

        self.process_and_flush_pending_tasks()

        self.assertEqual(
            stats_models.StateHitEventLogEntryModel.query().count(), 1)
        self.assertEqual(
            stats_models.MaybeLeaveExplorationEventLogEntryModel.query().count(),
            2)
        self.assertEqual(
            stats_jobs.NullStateHitEventsMigrator.get_output(new_job_id), [])

        target_item = None
        for item in stats_models.MaybeLeaveExplorationEventLogEntryModel.query():
            if item.session_id == 'bad_session_id_1':
                target_item = item

        self.assertIsNotNone(target_item)
        self.assertNotEqual(source_item, target_item)
        self.assertNotEqual(source_item.id, target_item.id)
        self.assertEqual(
            target_item.event_type, feconf.EVENT_TYPE_MAYBE_LEAVE_EXPLORATION)
        self.assertEqual(
            source_item.exploration_id, target_item.exploration_id)
        self.assertEqual(
            source_item.exploration_version, target_item.exploration_version)
        self.assertEqual(target_item.state_name, feconf.END_DEST)
        self.assertEqual(target_item.client_time_spent_in_secs, 0)
        self.assertEqual(source_item.params, target_item.params)
        self.assertEqual(source_item.play_type, target_item.play_type)
        self.assertEqual(source_item.created_on, target_item.created_on)
        # It is not possible to set the last_updated field explicitly.
        self.assertLess(source_item.last_updated, target_item.last_updated)
        self.assertEqual(source_item.deleted, target_item.deleted)
        self.assertEqual(target_item.deleted, False)
