import os
import unittest

from bugwarrior.config import schema

from ..base import ConfigTest


class TestLoggingPath(unittest.TestCase):
    def setUp(self):
        self.dir = os.getcwd()
        os.chdir(os.path.expanduser('~'))

    def test_log_relative_path(self):
        self.assertEqual(
            schema.LoggingPath.validate('bugwarrior.log'),
            'bugwarrior.log',
        )

    def test_log_absolute_path(self):
        filename = os.path.join(os.path.expandvars('$HOME'), 'bugwarrior.log')
        self.assertEqual(
            schema.LoggingPath.validate(filename),
            'bugwarrior.log',
        )

    def test_log_userhome(self):
        self.assertEqual(
            schema.LoggingPath.validate('~/bugwarrior.log'),
            'bugwarrior.log',
        )

    def test_log_envvar(self):
        self.assertEqual(
            schema.LoggingPath.validate('$HOME/bugwarrior.log'),
            'bugwarrior.log',
        )

    def tearDown(self):
        os.chdir(self.dir)


class TestConfigList(unittest.TestCase):
    def test_configlist(self):
        self.assertEqual(
            schema.ConfigList.validate('project_bar,project_baz'),
            ['project_bar', 'project_baz']
        )

    def test_configlist_jinja(self):
        self.assertEqual(
            schema.ConfigList.validate(
                "work, jira, {{jirastatus|lower|replace(' ','_')}}"),
            ['work', 'jira', "{{jirastatus|lower|replace(' ','_')}}"]
        )


class TestValidation(ConfigTest):
    def setUp(self):
        super().setUp()
        self.config = {
            'general': {'targets': ['my_service', 'my_kan', 'my_gitlab']},
            'my_service': {
                'service': 'github',
                'login': 'ralph',
                'username': 'ralph',
                'token': 'abc123',
            },
            'my_kan': {
                'service': 'kanboard',
                'url': 'https://kanboard.example.org',
                'username': 'ralph',
                'password': 'abc123',
            },
            'my_gitlab': {
                'service': 'gitlab',
                'host': 'my-git.org',
                'login': 'arbitrary_login',
                'token': 'arbitrary_token',
                'owned': 'false',
            },
        }

    def test_valid(self):
        self.validate()

    def test_main_section_required(self):
        del self.config['general']

        self.assertValidationError("No section: 'general'")

    def test_main_section_missing_targets_option(self):
        del self.config['general']['targets']

        self.assertValidationError("No option 'targets' in section: 'general'")

    def test_target_section_missing(self):
        del self.config['my_service']

        self.assertValidationError("No section: 'my_service'")

    def test_service_missing(self):
        del self.config['my_service']['service']

        self.assertValidationError(
            "No option 'service' in section: 'my_service'")

    def test_extra_field(self):
        """ Undeclared fields are forbidden. """
        self.config['my_service']['undeclared_field'] = 'extra'

        self.assertValidationError(
            '[my_service]\n'
            'undeclared_field  <- unrecognized option')

    def test_root_validator(self):
        del self.config['my_service']['username']

        self.assertValidationError(
            '[my_service]  <- '
            'section requires one of:\n    username\n    query')

    def test_no_scheme_url_validator_default(self):
        conf = self.validate()
        self.assertEqual(conf['my_service'].host, 'github.com')

    def test_no_scheme_url_validator_set(self):
        self.config['my_service']['host'] = 'github.com'
        conf = self.validate()
        self.assertEqual(conf['my_service'].host, 'github.com')

    def test_no_scheme_url_validator_scheme(self):
        self.config['my_service']['host'] = 'https://github.com'
        self.assertValidationError(
            "host  <- URL should not include scheme ('https')")

    def test_stripped_trailing_slash_url(self):
        self.config['my_kan']['url'] = 'https://kanboard.example.org/'
        conf = self.validate()
        self.assertEqual(conf['my_kan'].url, 'https://kanboard.example.org')

    def test_deprecated_filter_merge_requests(self):
        conf = self.validate()
        self.assertEqual(conf['my_gitlab'].include_merge_requests, True)

        self.config['my_gitlab']['filter_merge_requests'] = 'true'
        conf = self.validate()
        self.assertEqual(conf['my_gitlab'].include_merge_requests, False)

    def test_deprecated_filter_merge_requests_and_include_merge_requests(self):
        self.config['my_gitlab']['filter_merge_requests'] = 'true'
        self.config['my_gitlab']['include_merge_requests'] = 'true'
        self.assertValidationError(
            '[my_gitlab]  <- filter_merge_requests and include_merge_requests are incompatible.')

    def test_deprecated_project_name(self):
        """ We're just testing that deprecation doesn't break validation. """
        self.config['general']['targets'] = ['my_service', 'my_kan', 'my_gitlab', 'my_redmine']
        self.config['my_redmine'] = {
            'service': 'redmine',
            'url': 'https://example.com',
            'key': 'mykey',
        }
        self.validate()

        self.config['my_redmine']['project_name'] = 'myproject'
        self.validate()


class TestComputeTemplates(unittest.TestCase):
    def test_template(self):
        raw_values = {'templates': {}, 'project_template': 'foo'}
        computed_values = schema.ServiceConfig().compute_templates(raw_values)
        self.assertEqual(computed_values['templates'], {'project': 'foo'})

    def test_empty_template(self):
        """
        Respect setting field templates to an empty string.

        This should not be ignored but should make the corresponding task field
        an empty string.

        https://github.com/ralphbean/bugwarrior/issues/970
        """
        raw_values = {'templates': {}, 'project_template': ''}
        computed_values = schema.ServiceConfig().compute_templates(raw_values)
        self.assertEqual(computed_values['templates'], {'project': ''})
