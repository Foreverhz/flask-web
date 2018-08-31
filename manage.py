from flask import Flask, session, current_app
from flask_script import Manager
from info import create_app, db
from flask_migrate import Migrate, MigrateCommand
import logging
from info.models import User


# 单一职责的原则：manage.py 仅仅作为项目启动文件即可
# 工厂方法的调用（ofo公司）
app = create_app("development")

# 7. 创建manager管理类
manager = Manager(app)
# 初始化迁移对象
Migrate(app, db)
# 将迁移命令添加到管理对象中
manager.add_command("db", MigrateCommand)


# useage: python manage.py createsuperuser -n "admin" -p "123456"
@manager.option("-n", "-name", dest="name")
@manager.option("-p", "-password", dest="password")
def createsuperuser(name, password):
    """创建管理员用户"""
    if not all([name, password]):
        return "参数不足"
    user = User()
    user.is_admin = True
    user.nick_name = name
    user.mobile = name
    user.password = password

    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()

    print("创建管理员用户成功")




if __name__ == '__main__':
    manager.run()
