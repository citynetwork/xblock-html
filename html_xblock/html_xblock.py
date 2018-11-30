"""This XBlock help creating a secure and easy-to-use HTML blocks in edx-platform."""

import logging

import pkg_resources
from django.utils import translation
from xblock.core import XBlock
from xblock.fields import Boolean, Scope, String
from xblock.fragment import Fragment
from xblockutils.resources import ResourceLoader
from xblockutils.studio_editable import StudioEditableXBlockMixin, loader

from .bleaching import SanitizedText
from .utils import _

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
xblock_loader = ResourceLoader(__name__)  # pylint: disable=invalid-name


class HTML5XBlock(StudioEditableXBlockMixin, XBlock):
    """
    This XBlock will provide an HTML WYSIWYG interface in Studio to be rendered in LMS.
    """

    display_name = String(
        display_name=_('Display Name'),
        help=_('The display name for this component.'),
        scope=Scope.settings,
        default=_('Text')
    )
    data = String(help=_('Html contents to display for this module'), default=u'', scope=Scope.content)
    allow_javascript = Boolean(
        display_name=_('Allow JavaScript execution'),
        help=_('Whether JavaScript should be allowed or not in this module'),
        default=False,
        scope=Scope.content
    )
    editor = String(
        help=_(
            'Select Visual to enter content and have the editor automatically create the HTML. Select Raw to edit '
            'HTML directly. If you change this setting, you must save the component and then re-open it for editing.'
        ),
        display_name=_('Editor'),
        default='visual',
        values=[
            {'display_name': _('Visual'), 'value': 'visual'},
            {'display_name': _('Raw'), 'value': 'raw'}
        ],
        scope=Scope.settings
    )
    editable_fields = ('display_name', 'editor', 'allow_javascript')

    @staticmethod
    def resource_string(path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode('utf8')

    @XBlock.supports('multi_device')
    def student_view(self, context=None):  # pylint: disable=unused-argument
        """
        Return a fragment that contains the html for the student view
        """
        frag = Fragment()
        frag.content = xblock_loader.render_template('static/html/lms.html', {'self': self})

        frag.add_css(self.resource_string('public/plugins/codesample/css/prism.css'))
        frag.add_javascript(self.resource_string('public/plugins/codesample/js/prism.js'))

        return frag

    def studio_view(self, context=None):  # pylint: disable=unused-argument
        """
        Return a fragment that contains the html for the Studio view
        """
        frag = Fragment()

        settings_fields = self.get_editable_fields()
        settings_page = loader.render_template('templates/studio_edit.html', {'fields': settings_fields})
        context = {
            'self': self,
            'settings_page': settings_page,
        }

        frag.content = xblock_loader.render_template('static/html/studio.html', context)

        self.add_stylesheets(frag)

        # Add i18n js
        statici18n_js_url = self._get_statici18n_js_url()
        if statici18n_js_url:
            frag.add_javascript_url(self.runtime.local_resource_url(self, statici18n_js_url))

        self.add_scripts(frag)

        js_data = {
            'editor': self.editor,
            'skin_url': self.runtime.local_resource_url(self, 'public/skin'),
            'external_plugins': self.get_editor_plugins()
        }
        frag.initialize_js('HTML5XBlock', js_data)

        return frag

    @XBlock.json_handler
    def update_content(self, data, suffix=''):  # pylint: disable=unused-argument
        """
        Update the saved HTML data with the new HTML passed in the JSON 'content' field.
        """
        self.data = data['content']

        return {'content': self.data}

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ('HTML5XBlock',
             """<html5/>
             """),
            ('HTML5XBlock with sanitized content',
             """<html5 data="My custom &lt;b&gt;html&lt;/b&gt;"/>
             """),
            ('HTML5XBlock with JavaScript',
             """<html5
                    data="My custom &lt;b&gt;html&lt;/b&gt;&lt;script&gt;alert('With javascript');&lt;/script&gt;"
                    allow_javascript="true"
                />
             """),
            ('HTML5XBlock with JavaScript not allowed',
             """<html5
                    data="My custom &lt;b&gt;html&lt;/b&gt;&lt;script&gt;alert('With javascript');&lt;/script&gt;"
                    allow_javascript="false"
                />
             """),
            ('Multiple HTML5XBlock',
             """<vertical_demo>
                <html5/>
                <html5/>
                <html5/>
                </vertical_demo>
             """),
        ]

    def add_stylesheets(self, frag):
        """
        A helper method to add all necessary styles to the fragment.
        :param frag: The fragment that will hold the scripts.
        """
        frag.add_css(self.resource_string('static/css/html.css'))

        if self.editor == 'raw':
            frag.add_css(self.resource_string('public/plugins/codemirror/codemirror-4.8/lib/codemirror.css'))

    def add_scripts(self, frag):
        """
        A helper method to add all necessary scripts to the fragment.
        :param frag: The fragment that will hold the scripts.
        """
        frag.add_javascript(self.resource_string('static/js/tinymce/tinymce.min.js'))
        frag.add_javascript(self.resource_string('static/js/tinymce/themes/modern/theme.min.js'))
        frag.add_javascript(self.resource_string('static/js/html_xblock.js'))
        frag.add_javascript(loader.load_unicode('public/studio_edit.js'))

        if self.editor == 'raw':
            code_mirror_dir = 'public/plugins/codemirror/codemirror-4.8/'
            frag.add_javascript(self.resource_string(code_mirror_dir + 'lib/codemirror.js'))
            frag.add_javascript(self.resource_string(code_mirror_dir + 'mode/xml/xml.js'))

    def get_editor_plugins(self):
        """
        This method will generate a list of external plugins urls to be used in TinyMCE editor.
        These plugins should live in `public` directory for us to generate URLs for.

        const PLUGINS_DIR = "/resource/html5/public/plugins/";
        const EXTERNAL_PLUGINS = PLUGINS.map(function(p) { return PLUGINS_DIR + p + "/plugin.min.js" });

        :return: A list of URLs
        """
        plugin_path = 'public/plugins/{plugin}/plugin.min.js'
        plugins = ['codesample', 'image', 'link', 'lists', 'textcolor', 'codemirror']

        return {
            plugin: self.runtime.local_resource_url(self, plugin_path.format(plugin=plugin)) for plugin in plugins
        }

    @property
    def sanitized_html(self):
        """
        A property that returns a sanitized text field of the existing data object.
        """
        html = SanitizedText(self.data)
        return html.value

    @property
    def html(self):
        """
        A property that returns this module content data, according to `allow_javascript`.
        I.E: Sanitezed data if it's true or plain data if it's false.
        """
        if self.allow_javascript:
            return self.data
        return self.sanitized_html

    def get_editable_fields(self):
        """

        This method extracts the editable fields from this XBlock and returns
        them after validating them.

        Part of this method's copied from StudioEditableXBlockMixin#submit_studio_edits
        with some modifications..
        :return: A list of the editable fields with the information that
                the template needs to render a form field for them.

        """
        fields = []

        # Build a list of all the fields that can be edited:
        for field_name in self.editable_fields:
            field = self.fields[field_name]  # pylint: disable=unsubscriptable-object
            assert field.scope in (Scope.content, Scope.settings), _(
                'Only Scope.content or Scope.settings fields can be used with '
                'StudioEditableXBlockMixin. Other scopes are for user-specific data and are '
                'not generally created/configured by content authors in Studio.'
            )
            field_info = self._make_field_info(field_name, field)
            if field_info is not None:
                fields.append(field_info)

        return fields

    @staticmethod
    def _get_statici18n_js_url():
        """
        Returns the Javascript translation file for the currently selected language, if any.
        Defaults to English if available.
        """
        locale_code = translation.get_language()
        if locale_code is None:
            return None
        text_js = 'public/js/translations/{locale_code}/text.js'
        lang_code = locale_code.split('-')[0]
        for code in (locale_code, lang_code, 'en'):
            resource_loader = ResourceLoader(__name__)
            if pkg_resources.resource_exists(
                    resource_loader.module_name, text_js.format(locale_code=code)):
                return text_js.format(locale_code=code)
        return None

    @staticmethod
    def get_dummy():
        """
        Dummy method to generate initial i18n
        """
        return translation.gettext_noop('Dummy')
