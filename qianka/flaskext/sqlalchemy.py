# -*- coding: utf-8 -*-
from contextlib import contextmanager
from flask import _app_ctx_stack
from flask.ext.sqlalchemy import SignallingSession, SQLAlchemy, get_state


__all__ = ['QKSQLAlchemy']


_CTX_ATTR = '_sqlalchemy_use_bind_stack'


class QKSignallingSession(SignallingSession):
    def get_bind(self, mapper, clause=None):
        """Customize database query routing (master/salve or sharding) here
        """
        ctx = _app_ctx_stack.top
        stack = hasattr(ctx, _CTX_ATTR) and getattr(ctx, _CTX_ATTR, None)
        if isinstance(stack, list) and len(stack) > 0:
            bind_key = stack[-1]
            state = get_state(self.app)
            bind = state.db.get_engine(self.app, bind=bind_key)
            self.app.logger.debug('sqlalchemy_use_bind: %s' % bind_key)
            return bind

        return SignallingSession.get_bind(self, mapper, clause)


class QKSQLAlchemy(SQLAlchemy):
    def create_session(self, options):
        return QKSignallingSession(self, **options)

    @contextmanager
    def use_bind(self, bind_key=None):
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
