// Copyright 2014 The Oppia Authors. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS-IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Utilities for exploration creation, publication ect. when
 * carrrying out end-to-end testing with protractor.
 *
 * @author Jacob Davis (jacobdavis11@gmail.com)
 */

var forms = require('./forms.js');
var editor = require('./editor.js');
var general = require('./general.js');

// Creates an exploration and opens its editor.
var createExploration = function(name, category) {
  createExplorationAndStartTutorial(name, category);
  editor.exitTutorialIfNecessary();
};

// Creates a new exploration and wait for the exploration
// tutorial to start.
var createExplorationAndStartTutorial = function(name, category) {
  browser.get(general.GALLERY_URL_SUFFIX);
  element(by.css('.protractor-test-create-exploration')).click();
  protractor.getInstance().waitForAngular();
  element(by.css('.protractor-test-new-exploration-title')).sendKeys(name);
  forms.AutocompleteDropdownEditor(
    element(by.css('.protractor-test-new-exploration-category'))
  ).setValue(category);
  element(by.css('.protractor-test-submit-new-exploration')).click();

  // We now want to wait for the editor to fully load.
  protractor.getInstance().waitForAngular();
};

// This will only work if all changes have been saved and there are no
// outstanding warnings; run from the editor.
var publishExploration = function() {
  element(by.css('.protractor-test-publish-exploration')).click();
  protractor.getInstance().waitForAngular();
  general.waitForSystem();
  element(by.css('.protractor-test-confirm-publish')).click();
};

// Creates and publishes a minimal exploration
var createAndPublishExploration = function(name, category, objective, language) {
  createExploration(name, category);
  editor.setContent(forms.toRichText('new exploration'));
  editor.setInteraction('TextInput');
  editor.addRule('TextInput', null, 'END', 'Default');
  editor.setObjective(objective);
  if (language) {
    editor.setLanguage(language);
  }
  editor.setInteraction('Continue');
  editor.saveChanges();
  publishExploration();
};

// Run from the editor, requires user to be a moderator / admin.
var markExplorationAsFeatured = function() {
  editor.runFromSettingsTab(function() {
    element(by.css('.protractor-test-mark-exploration-featured')).click();
  });
};

// Role management (state editor settings tab)

// roleName here is the user-visible form of the role name (e.g. 'Manager')
var _addExplorationRole = function(roleName, username) {
  editor.runFromSettingsTab(function() {
    element(by.css('.protractor-test-edit-roles')).click();
    element(by.css('.protractor-test-role-username')).sendKeys(username);
    element(by.css('.protractor-test-role-select')).
      element(by.cssContainingText('option', roleName)).click();
    element(by.css('.protractor-test-save-role')).click();
  });
};

var addExplorationManager = function(username) {
  _addExplorationRole('Manager', username);
};

var addExplorationCollaborator = function(username) {
  _addExplorationRole('Collaborator', username);
};

var addExplorationPlaytester = function(username) {
  _addExplorationRole('Playtester', username);
};

// roleName here is the server-side form of the name (e.g. 'owner')
var _getExplorationRoles = function(roleName) {
  var result = editor.runFromSettingsTab(function() {
    var itemName = roleName + 'Name';
    var listName = roleName + 'Names';
    return element.all(by.repeater(
          itemName + ' in explorationRightsService.' + listName + ' track by $index'
        )).map(function(elem) {
      return elem.getText();
    });
  });
  return result;
};

var getExplorationManagers = function() {
  return _getExplorationRoles('owner');
};

var getExplorationCollaborators = function() {
  return _getExplorationRoles('editor');
};

var getExplorationPlaytesters = function() {
  return _getExplorationRoles('viewer');
};

exports.createExploration = createExploration;
exports.createExplorationAndStartTutorial = createExplorationAndStartTutorial;
exports.publishExploration = publishExploration;
exports.createAndPublishExploration = createAndPublishExploration;
exports.markExplorationAsFeatured = markExplorationAsFeatured;

exports.addExplorationManager = addExplorationManager;
exports.addExplorationCollaborator = addExplorationCollaborator;
exports.addExplorationPlaytester = addExplorationPlaytester;
exports.getExplorationManagers = getExplorationManagers;
exports.getExplorationCollaborators = getExplorationCollaborators;
exports.getExplorationPlaytesters = getExplorationPlaytesters;
