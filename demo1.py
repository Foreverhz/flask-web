# class Person(object):
#
#     def __eq__(self, other):
#         return "hhh"
#
#     def __init__(self):
#         self.password_hash = ""
#
#     # get方法（获取属性的值）
#     @property
#     def password(self):
#         print("get方法被触发了")
#
#     # set方法（给属性设置值）
#     @password.setter
#     def password(self, value):
#         # 加密处理
#         print("set方法被触发了 %s" %value)
#
#
# if __name__ == '__main__':
#     p = Person()
#     p.password = "1234"
#     p1 = Person()
#
#     print(p==p1)
#     # print(p.password)


#------------------------------------------

# import functools
#
# def user_login_data(view_func):
#
#     @functools.wraps(view_func)
#     def wrapper(*args , **kwargs):
#         # 你的需求(装饰)
#
#         # 执行原有的功能
#         result = view_func(*args, **kwargs)
#         return result
#     return wrapper
#
# @user_login_data
# def index():
#
#     print("index")
#
# @user_login_data
# def hello():
#     print("hello")
#
# if __name__ == '__main__':
#     print(index.__name__)
#     print(hello.__name__)



#------------------------------------------
import datetime
import random

from info import db
from info.models import User
from manage import app


def add_test_users():
    users = []
    now = datetime.datetime.now()
    for num in range(0, 10000):
        try:
            user = User()
            user.nick_name = "%011d" % num
            user.mobile = "%011d" % num
            user.password_hash = "pbkdf2:sha256:50000$SgZPAbEj$a253b9220b7a916e03bf27119d401c48ff4a1c81d7e00644e0aaf6f3a8c55829"
            # 当前时间往前面推一个随机时间作为用户的最后一次登录时间（31天）
            user.last_login = now - datetime.timedelta(seconds=random.randint(0, 2678400))
            users.append(user)
            print(user.mobile)
        except Exception as e:
            print(e)
    # 手动开启app上下文
    with app.app_context():
        db.session.add_all(users)
        db.session.commit()
    print('OK')


if __name__ == '__main__':
    add_test_users()











