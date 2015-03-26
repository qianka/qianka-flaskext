# -*- coding: utf-8 -*-
"""
https://github.com/fengsp/flask-session
"""
from flask.sessions import SessionMixin, SessionInterface
import hashlib
import msgpack
from uuid import uuid4
from werkzeug.datastructures import CallbackDict


class ServerSideSession(CallbackDict, SessionMixin):
    """Baseclass for server-side based sessions."""

    def __init__(self, initial=None, sid=None):
        def on_update(self):
            self.modified = True
        CallbackDict.__init__(self, initial, on_update)
        self.sid = sid
        self.permanent = True
        self.modified = False
        self.new = initial is None


class RedisSession(ServerSideSession):
    """
    placeholder
    """
    pass


class RedisSessionInterface(SessionInterface):
    """
    使用服务端的 Redis 保存访问者 session，采用 msgpack 序列化数据
    """

    serializer = msgpack
    session_class = RedisSession

    def __init__(self, redis=None, key_prefix='session:'):
        """Uses the Redis key-value store as a session backend.
        :param redis: A ``redis.StrictRedis`` instance.
        :param key_prefix: A prefix that is added to all Redis store keys.
        """
        if redis is None:
            from redis import StrictRedis
            redis = StrictRedis()
        self.redis = redis
        self.key_prefix = key_prefix

    @staticmethod
    def encode_sid(sid, salt):
        """
        编码 session_id，并增加校验码，使得该 ID 不容易被猜测
        :param sid: 原始编号，服务端 redis 里使用的编号
        :param salt: 共享密钥
        :return: 编码过的 sid
        """
        if not isinstance(sid, str):
            return None
        m = hashlib.sha1((sid + salt).encode('utf8')).hexdigest()
        return '%s%s%s' % (m[:3], sid, m[-3:])

    @staticmethod
    def decode_sid(data, salt):
        """
        解码并验证 session_id
        :param data: 编码过的 sid，客户端 cookie 里存放的编号
        :param salt: 共享密钥
        :return: 原始编号；如果验证错误，返回 None
        """
        if not isinstance(data, str) or len(data) < 6:
            return None
        sid = data[3:-3]
        m = hashlib.sha1((sid + salt).encode('utf8')).hexdigest()
        if m[:3] == data[:3] and m[-3:] == data[-3:]:
            return sid
        return None

    def open_session(self, app, request):
        """
        从 redis 里获取 session 的内容
        :param app:
        :param request:
        :return:
        """
        sid = request.cookies.get(app.session_cookie_name)
        sid = self.decode_sid(sid, app.secret_key)
        if not sid:
            sid = uuid4().hex
            return self.session_class(sid=sid)
        val = self.redis.get(self.key_prefix + sid)
        if val is not None:
            try:
                data = self.serializer.loads(val, encoding='utf8')
                return self.session_class(data, sid=sid)
            except Exception as e:
                app.logger.warning(e)
                return self.session_class(sid=sid)
        return self.session_class(sid=sid)

    def save_session(self, app, session, response):
        """
        保存 session 内容至 redis
        :param app:
        :param session:
        :param response:
        :return:
        """
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        if not session:
            # 删除 session
            if session.modified:
                self.redis.delete(self.key_prefix + session.sid)
                response.delete_cookie(app.session_cookie_name,
                                       domain=domain, path=path)
            return

        if not session.new and not session.modified:
            return

        # 保存改动过的 session包括新建立的
        httponly = self.get_cookie_httponly(app)
        secure = self.get_cookie_secure(app)
        expires = self.get_expiration_time(app, session)
        val = self.serializer.dumps(dict(session), use_bin_type=True, encoding='utf8')
        self.redis.setex(self.key_prefix + session.sid,
                         int(app.permanent_session_lifetime.total_seconds()),
                         val)
        sid = self.encode_sid(session.sid, app.secret_key)
        response.set_cookie(app.session_cookie_name, sid,
                            expires=expires, httponly=httponly,
                            domain=domain, path=path, secure=secure)
