# -*- coding: utf-8 -*-
import os
from flask import Flask, current_app
from webassets.ext.jinja2 import Jinja2Loader
from webassets.script import GenericArgparseImplementation

__all__ = ['QKFlask']


class QKFlask(Flask):
    """
    Flask Application

    - add_url_rule()
    - register_asset()
    - prepare_templates()
    - prepare_webassets()
    - prepare_celery()
    - build_assets()
    - HTML_COMPRESS
    - CDN_URL_PREFIX_STATIC
    - CDN_URL_PREFIX_ASSETS
    """
    def __init__(self, import_name, static_path=None, static_url_path=None,
                 static_folder='static', template_folder='templates',
                 instance_path=None, instance_relative_config=False,
                 bower_components_folder=None):
        super(QKFlask, self).__init__(
            import_name,
            static_path, static_url_path, static_folder, template_folder,
            instance_path, instance_relative_config
        )

        self.bower_components_folder = bower_components_folder
        self.config.setdefault('HTML_COMPRESS', False)
        self.config.setdefault('CDN_URL_PREFIX_STATIC', '')
        self.config.setdefault('CDN_URL_PREFIX_ASSETS', '')

        self.webassets = None

    def add_url_rule(self, rule, endpoint=None, view_func=None, **options):
        """
        Override. The argument endpoint becomes optional and equals rule by default
        """
        if endpoint is None:
            endpoint = rule

        super(QKFlask, self).add_url_rule(
            rule,
            endpoint=endpoint,
            view_func=view_func,
            **options
        )

    def register_asset(self, name, *assets):
        """
        合并、预处理资源文件，并注册至 webassets。

        :param name: 在页面调用时使用的文件名
        :param assets: 资源文件源文件列表
        :return:

        最后输出的文件名为 `{name}.{hash}.css` 或 `{name}.{hash}.js`。其中 hash 与内容相关。
        """
        if self.webassets is None:
            raise Exception('webassets is not ready. init_app() should be invoked')

        if not assets:
            assets = [name]

        from flask.ext.assets import Bundle
        bundles = []
        for asset in assets:
            if isinstance(asset, str):
                asset_file = asset
                asset_filters = self._detect_filters_by_ext(asset_file)
            else:
                asset_file, asset_filters = asset

            bundle = Bundle(
                asset_file, depends=[asset_file], filters=tuple(asset_filters)
            )

            bundles.append(bundle)

        fn, fe = os.path.splitext(name)
        output = '%s.%%(version)s%s' % (fn, fe)
        self.webassets.register(name, *bundles, output=output)

    @staticmethod
    def _detect_filters_by_ext(filename):
        filter_map = {
            '.jinja':  ['jinja2'],
            '.styl':   ['stylus', 'cssmin'],
            '.coffee': ['coffeescript', 'uglifyjs'],
            '.css':    ['cssmin'],
            '.js':     ['uglifyjs']
        }
        filters = []
        while True:
            fn, fe = os.path.splitext(filename)
            if not fe:
                return filters
            if fe in filter_map:
                filters.extend(filter_map[fe])
            filename = fn

    def select_jinja_autoescape(self, filename):
        if filename is None:
            return False
        if super(QKFlask, self).select_jinja_autoescape(filename):
            return True
        return filename.endswith(('.html.jinja', '.htm.jinja', '.xml.jinja', '.xhtml.jinja'))

    def prepare_templates(self):
        """
        - 支持 HTML 压缩，`{% strip %} ... {% endstrip %}`
        - 纯静态文件 URL 路径 `/static`
        - 可配置 CDN 域名及路径前缀。`url_for(endpoint='static')`
        """
        # HTML_compress
        from . import jinja2htmlcompress
        if self.config['HTML_COMPRESS']:
            jinja2htmlcompress.enabled = True
        self.jinja_env.add_extension("%s.%s" % (
            jinja2htmlcompress.SelectiveHTMLCompress.__module__,
            jinja2htmlcompress.SelectiveHTMLCompress.__name__)
        )

        # url_for that supports CDN
        origin_url_for = self.jinja_env.globals['url_for']

        def url_for(endpoint, **values):
            url = origin_url_for(endpoint, **values)

            external = values.pop('_external', False)
            if external:
                return url

            if endpoint == 'static':
                url = self.config['CDN_URL_PREFIX_STATIC'] + url
            return url

        self.jinja_env.globals['url_for'] = url_for

    def prepare_webassets(self):
        """
        - webassets 资源文件
        - 资源文件 URL 路径 `/assets`
        - 可配置 CDN 域名及路径前缀。`url_for(endpoint='assets')`
        """
        import flask.ext.assets

        self.webassets = flask.ext.assets.Environment(self)

        self.webassets.url = '%s/assets' % self.config['CDN_URL_PREFIX_ASSETS']
        if self.template_folder.startswith('/'):
            self.webassets.append_path(self.template_folder)
        else:
            self.webassets.append_path(os.path.abspath('%s/%s' % (self.root_path, self.template_folder)))
        if self.bower_components_folder is not None:
            if self.bower_components_folder.startswith('/'):
                self.webassets.append_path(self.bower_components_folder)
            else:
                self.webassets.append_path(os.path.abspath('%s/%s' % (self.root_path, self.bower_components_folder)))

        if self.webassets.config.get('directory'):
            self.logger.info("assets.directory: %s" % self.webassets.directory)
        else:
            import tempfile
            self.webassets.directory = tempfile.mkdtemp()
            self.logger.warn("assets.directory: %s" % self.webassets.directory)

        def _send_assets_file(filename):
            cache_timeout = self.get_send_file_max_age(filename)
            return flask.send_from_directory(
                self.webassets.directory, filename, cache_timeout=cache_timeout)

        self.add_url_rule(
            '/assets/<path:filename>',
            endpoint='assets',
            view_func=_send_assets_file
        )

    def build_assets(self, args=None):
        """
        :param args: the command line arguments
        :return:
        """
        if args is None:
            args = ['-v', 'build']

        with self.app_context():
            if not hasattr(current_app.jinja_env, 'assets_environment'):
                self.logger.warn("Assets environment not found.")
                return
            impl = FlaskArgparseInterface(current_app.jinja_env.assets_environment)
            impl.main(args)

    def prepare_celery(self, celery):
        """
        确保异步任务在 appctx 下执行
        :param celery:
        :return:
        """
        _TaskBase = celery.Task
        outter = self

        class ContextTask(_TaskBase):
            abstract = True

            def __call__(self, *args, **kwargs):
                with outter.app_context():
                    return _TaskBase.__call__(self, *args, **kwargs)

        celery.Task = ContextTask


class FlaskArgparseInterface(GenericArgparseImplementation):

    def _setup_assets_env(self, ns, log):
        env = super(FlaskArgparseInterface, self)._setup_assets_env(ns, log)
        log.info('Searching templates...')
        # Note that we exclude container bundles. By their very nature,
        # they are guaranteed to have been created by solely referencing
        # other bundles which are already registered.
        env.add(*[b for b in self.load_from_templates(env, log)
                        if not b.is_container])

        return env

    @staticmethod
    def load_from_templates(env, log):
        # Use the application's Jinja environment to parse
        jinja2_env = current_app.jinja_env

        # Get the template directories of app and blueprints
        template_dirs = [
            os.path.join(current_app.root_path, current_app.template_folder)
        ]
        for blueprint in current_app.blueprints.values():
            if blueprint.template_folder is None:
                continue
            template_dirs.append(
                os.path.join(blueprint.root_path, blueprint.template_folder))

        log.info('Loading templates from: %s' % template_dirs)
        loader = Jinja2Loader(env, template_dirs, [jinja2_env], jinja_ext='*.*')
        return loader.load_bundles()
