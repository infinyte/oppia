# Copyright 2012 Google Inc. All Rights Reserved.
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

"""Controllers for the Oppia reader view."""

__author__ = 'Sean Lip'

import json, logging, os, random
from controllers.base import BaseHandler
import classifiers, feconf, models, utils

from google.appengine.api import users
from google.appengine.ext import ndb

DEFAULT_CATALOG_CATEGORY_NAME = 'Miscellaneous'
READER_MODE = 'reader'


class ExplorationPage(BaseHandler):
  """Page describing a single exploration."""

  def get(self, exploration_id):  # pylint: disable-msg=C6409
    """Handles GET requests.

    Args:
      exploration_id: string representing the exploration id.
    """
    self.values.update({
        'js': utils.GetJsFilesWithBase(['readerExploration']),
        'nav_mode': READER_MODE,
    })

    # The following is needed for embedding Oppia explorations in other pages.
    if self.request.get('iframed') == 'true':
      self.values['iframed'] = True

    self.response.out.write(feconf.JINJA_ENV.get_template(
        'reader/reader_exploration.html').render(self.values))


class ExplorationHandler(BaseHandler):
  """Provides the data for a single exploration."""

  def get(self, exploration_id):  # pylint: disable-msg=C6409
    """Populates the data on the individual exploration page.

    Args:
      exploration_id: string representing the exploration id.
    """
    # TODO(sll): This should send a complete state machine to the frontend.
    # All interaction would happen client-side.
    exploration = utils.GetEntity(models.Exploration, exploration_id)
    logging.info(exploration.init_state)
    init_state = exploration.init_state.get()
    init_html, init_widgets = utils.ParseContentIntoHtml(init_state.content, 0)
    self.data_values.update({
        'block_number': 0,
        'default_answer': classifiers.DEFAULT_ANSWER[
            init_state.input_view.get().classifier],
        'html': init_html,
        'input_view': init_state.input_view.get().name,
        'state_id': init_state.hash_id,
        'title': exploration.title,
        'widgets': init_widgets,
    })
    self.data_values['input_template'] = utils.GetInputTemplate(self.data_values['input_view'])
    if self.data_values['input_view'] == utils.input_views.multiple_choice:
      self.data_values['categories'] = init_state.classifier_categories
    self.response.out.write(json.dumps(self.data_values))

  def post(self, exploration_id, state_id):  # pylint: disable-msg=C6409
    """Handles feedback interactions with readers.

    Args:
      exploration_id: string representing the exploration id.
      state_id: string representing the state id.
    """
    values = {'error': []}

    exploration = utils.GetEntity(models.Exploration, exploration_id)
    state = utils.GetEntity(models.State, state_id)
    old_state = state
    # The reader's answer.
    response = self.request.get('answer')
    # The 0-based index of the last content block already on the page.
    block_number = int(self.request.get('block_number'))
    category = classifiers.Classify(state.input_view.get().classifier, response,
                                    state.classifier_categories)
    try:
      action_set = state.action_sets[category].get()
    except IndexError:
      # TODO(sll): handle the following error more gracefully. Perhaps use the
      # default category?
      logging.error('No action set found for response %s', response)
      return

    html_output = ''
    widget_output = []
    # Append reader's response.
    if state.input_view.get().classifier == 'finite':
      html_output = feconf.JINJA_ENV.get_template(
          'reader_response.html').render(
              {'response': state.classifier_categories[int(response)]})
    else:
      html_output = feconf.JINJA_ENV.get_template(
          'reader_response.html').render({'response': response})

    if not action_set.dest:
      # This leads to a FINISHED state.
      if action_set.text:
        action_html, action_widgets = utils.ParseContentIntoHtml(
            [{'type': 'text', 'value': action_set.text}], block_number)
        html_output += action_html
        widget_output.append(action_widgets)
    else:
      if action_set.dest_exploration:
        self.redirect('/learn/%s' % action_set.dest_exploration)
        return
      else:
        state = action_set.dest.get()

      # Append Oppia's feedback, if any.
      # TODO(sll): Rewrite this once the action_set.text becomes a content
      #     array.
      if action_set.text:
        action_html, action_widgets = utils.ParseContentIntoHtml(
            [{'type': 'text', 'value': action_set.text}], block_number)
        html_output += action_html
        widget_output.append(action_widgets)
      # Append text for the new state only if the new and old states differ.
      if old_state.hash_id != state.hash_id:
        state_html, state_widgets = utils.ParseContentIntoHtml(
            state.content, block_number)
        html_output += state_html
        widget_output.append(state_widgets)

    values['default_answer'] = classifiers.DEFAULT_ANSWER[
        state.input_view.get().classifier]
    values['exploration_id'] = exploration.hash_id
    values['state_id'] = state.hash_id
    values['html'] = html_output
    values['widgets'] = widget_output
    values['block_number'] = block_number + 1
    if not action_set.dest:
      values['input_view'] = utils.input_views.finished
    else:
      values['input_view'] = state.input_view.get().name
      if values['input_view'] == utils.input_views.multiple_choice:
        values['categories'] = state.classifier_categories
    values['input_template'] = utils.GetInputTemplate(values['input_view'])
    utils.Log(values)
    self.response.out.write(json.dumps(values))


class RandomExplorationPage(BaseHandler):
  """Returns the page for a random exploration."""

  def get(self):
    """Handles GET requests."""
    explorations = models.Exploration.query().filter(
        models.Exploration.is_public == True).fetch(100)

    selected_exploration = random.choice(explorations)

    self.redirect('/learn/%s' % selected_exploration.hash_id)