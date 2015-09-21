# -*- coding: utf-8 -*-
from contextlib import contextmanager

from flask.globals import _app_ctx_stack

from qianka.sqlalchemy import QKSession as SessionBase
from qianka.sqlalchemy import QKSQLAlchemy


__all__ = ['QKSQLAlchemy', 'QKSession', 'QKShardSession']

_CTX_ATTR = '_sqlalchemy_e7c4ed555c3ad9d68c4f4054efd80a40'  # md5(_sqlalchemy_use_bind_stack)


class QKSession(SessionBase):
    """ 支持 db.use_bind() 方法选择数据库连接
    """
    def __init__(self, db, **kwargs):
        super(QKSession, self).__init__(db, **kwargs)
        self.app = db.app

    def get_bind(self, *args, **kwargs):
        """ Customize database query routing (master/salve or sharding) here
        """
        ctx = _app_ctx_stack.top
        stack = hasattr(ctx, _CTX_ATTR) and getattr(ctx, _CTX_ATTR, None)
        if isinstance(stack, list) and len(stack) > 0:
            bind_key = stack[-1]
            engine = self.db.get_engine(bind_key)
            self.app.logger.debug('sqlalchemy_use_bind: %s' % bind_key)
            return engine

        return super(QKSession, self).get_bind(*args, **kwargs)


class QKFlaskSQLAlchemy(object):
    """ 在 Flask 中使用 SQLAlchemy
    Usage:
        app = Flask(__name__)
        db = QKFlaskSQLAlchemy(QKSQLAlchemy())
        db.init_app(app)

    - 传统单 session 用法:
        db.session.query(...)
    - 支持多 session 用法：
        db.get_session('master').query(...)
    """
    def __init__(self, db, app=None):
        print(db)
        # if isinstance(db, QKSQLAlchemy):
        #     raise ValueError("db shoud be instance of %r" % type(QKSQLAlchemy))
        self.db = db
        if app:
            self.init_app(app)

    def init_app(self, app):
        """
        :param app:
        :return:
        """
        self.db.app = app
        self.db.configure(self.db.app.config)

        self.db.scopefunc = _app_ctx_stack.__ident_func__

        @app.teardown_appcontext
        def shutdown_session(response_or_exc):
            self.db.reset()
            return response_or_exc

    @contextmanager
    def use_bind(self, bind_key):
        """Specify bind(engine/connection) for the current session
        :param bind_key: SQLALCHEMY_BINDS configured key

        Usage::

            with db.use_bind('slave'):
                User.query.filter(...)
        """
        ctx = _app_ctx_stack.top
        stack = hasattr(ctx, _CTX_ATTR) and getattr(ctx, _CTX_ATTR, None)
        try:
            if not isinstance(stack, list):
                stack = []
                setattr(ctx, _CTX_ATTR, stack)
            stack.append(bind_key)
            yield
        finally:
            stack.pop()

    ###

    @property
    def config(self):
        return self.db.config

    def configure(self, config=None, **kwargs):
        return self.db.configure(config, **kwargs)

    def reset(self):
        return self.db.reset()

    def create_session(self, engine=None, shard=False):
        return self.db.create_session(engine, shard)

    def get_session(self, bind_key=None):
        return self.db.get_session(bind_key)

    @property
    def session(self):
        return self.db.session

    def create_engine(self, uri):
        return self.db.create_engine(uri)

    def get_engine(self, bind_key=None):
        return self.db.get_engine(bind_key)

    @property
    def engine(self):
        return self.db.engine

    def reflect_model(self, table_name, bind_key=None):
        return self.db.reflect_model(table_name, bind_key)

