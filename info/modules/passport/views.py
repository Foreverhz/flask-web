from flask import session
from . import passport_bp
from flask import request, abort, current_app, make_response, jsonify
from info.utils.captcha.captcha import captcha
from info import redis_store
from info.utils.response_code import RET
from info import constants, db
import re
from info.models import User
from info.lib.yuntongxun.sms import CCP
import json
import random
from datetime import datetime


# 127.0.0.1：5000/passport/login_out POST
@passport_bp.route('/login_out', methods=["POST"])
def login_out():
    """退出登录接口"""

    # 清除session数据退出登录
    session.pop("user_id", None)
    session.pop("nick_name", None)
    session.pop("mobile", None)
    # 防止管理员登录后退出的时候没有清除session数据导致普通用户也能登录管理员首页
    session.pop("is_admin", None)

    return jsonify(errno=RET.OK, errmsg="退出登录成功")


@passport_bp.route('/login', methods=["POST"])
def login():
    """用户登录接口"""
    """
    1.获取参数
        1.1 获取手机号码 密码（未加密）
    2.校验参数
        2.1 判断是否为空
        2.2 手机号码格式校验
    3.逻辑处理
        3.1 根据手机号码查询用户
        3.2 用户填写的密码和用户之前设置密码进行比较
        3.2 一致：登录成功 使用session记录用户信息
    4.返回值处理
    """

    # 1.1 手机号码 密码
    params_dict = request.json
    mobile = params_dict.get("mobile")
    password = params_dict.get("password")

    # 2.1 手机号码 短信验证码 密码非空判断
    if not all([mobile, password]):
        # 返回错误给前端展示
        return jsonify(errno=RET.PARAMERR, errmsg="提交参数不足")
    # 2.2 手机号码格式校验
    if not re.match('1[3578][0-9]{9}', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")

    #3.1 根据手机号码查询用户
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="从mysql查询用户异常")
    if not user:
        # 用户不存在
        return jsonify(errno=RET.NODATA, errmsg="用户不存在")

    #3.2 用户填写的密码和用户之前设置密码进行比较
    if not user.check_passowrd(password):
        return jsonify(errno=RET.PARAMERR, errmsg="密码填写错误")

    #3.2 一致：登录成功 使用session记录用户信息
    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile

    # 记录最后一次登录时间 (修改对象属性值)
    user.last_login = datetime.now()

    # 对模型对象进行增删改查之后需要再次提交这种变更关联到数据库
    # 如果你不像commit()就要去设置数据库的相关的配置属性（SQLALCHEMY_COMMIT_ON_TEARDOWN = True）
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="提交到数据库异常")

    #4.返回值处理
    return jsonify(errno=RET.OK, errmsg="登录成功")



@passport_bp.route('/register', methods=["POST"])
def register():
    """注册接口"""
    """
    1.获取参数
        1.1 手机号码 短信验证码 密码
    2.校验参数
        2.1 手机号码 短信验证码 密码非空判断
        2.2 手机号码验证
    3.逻辑处理
        3.1 根据手机号码的keySMS_18520340803去redis中获取真实的短信验证码
        3.2 对比用户填写的短信验证码和真实的短信验证是否一致
        3.3 一致：创建用户对象给里面的属性赋值，存储到mysql数据库User表里面去
        3.4 一般注册成功就代表你有登录过一次，可以使用session记录你的登录状态
    4.返回值处理
    """
    #1.1 手机号码 短信验证码 密码
    params_dict = request.json
    mobile = params_dict.get("mobile")
    smscode = params_dict.get("smscode")
    password = params_dict.get("password")

    #2.1 手机号码 短信验证码 密码非空判断
    if not all([mobile, smscode, password]):
        # 返回错误给前端展示
        return jsonify(errno=RET.PARAMERR, errmsg="提交参数不足")
    #2.2 手机号码格式校验
    if not re.match('1[3578][0-9]{9}', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")

    #3.1 根据手机号码的key SMS_18520340803去redis中获取真实的短信验证码
    try:
        real_sms_code = redis_store.get("SMS_%s" % mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="获取真实短信验证码异常")

    if not real_sms_code:
        # 表示短信验证码过期
        return jsonify(errno=RET.NODATA, errmsg="短信验证码过期")

    #3.2 对比用户填写的短信验证码和真实的短信验证是否一致
    if real_sms_code != smscode:
        return jsonify(errno=RET.DATAERR, errmsg="短信验证码填写错误")

    #3.3 一致：创建用户对象给里面的属性赋值，存储到mysql数据库User表里面去
    # 创建用户对象给属性赋值
    user = User()
    user.nick_name = mobile
    user.mobile = mobile
    #TODO:对密码进行赋值（加密）
    # 触发了底层的set方法进而在set方法里面进行加密处理
    user.password = password

    # 获取当前时间作为最后一次登录时间
    user.last_login = datetime.now()
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 数据库回滚
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="添加用户到数据库异常")

    #3.4 一般注册成功就代表你有登录过一次，可以使用session记录你的登录状态
    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile

    #4.返回注册成功的响应
    return jsonify(errno=RET.OK, errmsg="注册成功")



# /passport/sms_code
@passport_bp.route('/sms_code', methods=["POST"])
def send_sms():
    """点击发送短信验证码接口"""
    """
    1.获取参数
        1.1 手机号码，用户填写的图片验证码真实值，编号
    2.校验参数
        2.1 判断 手机号码，用户填写的图片验证码真实值，编号是否为空
        2.2 手机号码格式校验
    3.逻辑处理
        3.1 根据编号去获取redis中存储的图片验证码真实值
            3.1.1 image_code_id有值，删除
            3.1.2 image_code_id没有值，表示编号过期
        3.2 对比用户填写的真实值和后端获取的验证码真实值是否一致
        一致：发送短信验证码
        不一致：验证码填写错误
        3.3 保存短信验证码到redis
    4.返回值处理
    """
    #1.获取参数（json类型参数）
    #1.1 手机号码，用户填写的图片验证码真实值，编号
    #request.json 获取到数据会自动转换成python对象（dict or list）
    param_dict = request.json
    mobile = param_dict.get("mobile")
    image_code = param_dict.get("image_code")
    image_code_id = param_dict.get("image_code_id")

    #2.校验参数
    #2.1 判断 手机号码，用户填写的图片验证码真实值，编号是否为空
    if not all([mobile, image_code, image_code_id]):
        # 返回错误给前端展示
        return jsonify(errno=RET.PARAMERR, errmsg="提交参数不足")
    #2.2 手机号码格式校验
    if not re.match('1[3578][0-9]{9}', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")

    # 3.逻辑处理
    try:
        #3.1 根据编号去获取redis中存储的图片验证码真实值
        real_image_code = redis_store.get("imagecode_%s" %image_code_id)
        # 3.1.1 image_code_id有值，删除 防止下次多次使用同一个real_image_code来访问
        if real_image_code:
            redis_store.delete("imagecode_%s" %image_code_id)
    except Exception as e:
        # 记录日志
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg="查询图片验证码异常")

    #3.1.2 image_code_id没有值，表示编号过期
    if not real_image_code:
        return jsonify(errno=RET.NODATA, errmsg="验证码真实值过期")

    #3.2 对比用户填写的真实值和后端获取的验证码真实值是否一致
    if image_code.lower() != real_image_code.lower():
        return jsonify(errno=RET.DATAERR, errmsg="图片验证码填写错误")

    # 一致：发送短信验证码
    # 查看手机号码是否注册过
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        return jsonify(errno=RET.DATAERR, errmsg="查询用户手机号码是否存在异常")
    # 已经注册过了
    if user:
        return jsonify(errno=RET.DATAEXIST, errmsg="用户已经注册过")

    #1. 生成短信验证码随机值
    sms_code = random.randint(0, 999999)
    sms_code = "%06d" %sms_code
    #2. 调用云通讯发送短信验证码
    result = CCP().send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES/60], 1)
    # 发送短信验证码失败
    if result != 0:
        return jsonify(errno=RET.THIRDERR, errmsg="发送短信验证码失败")

    #3.发送短信验证码成功
    try:
        redis_store.set("SMS_%s" %mobile, sms_code, ex=constants.SMS_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="存储短信验证码真实值失败")

    # 返回值处理
    return jsonify(errno=RET.OK, errmsg="发送短信验证码成功，请注意查收")


# 127.0.0.1:5000/passport/image_code?imageCodeId=编号
@passport_bp.route('/image_code')
def get_imagecode():
    """
    图片验证码的后端接口(GET)
    1. 获取参数
        1.1 获取前端携带的imageCodeId编号
    2. 校验参数
        2.1 imageCodeId编号是否有值
    3. 逻辑处理
        3.0 生成验证码图片&验证码图片的真实值
        3.1 使用imageCodeId编号作为key存储生成的图片验证码真实值
    4. 返回值处理
        4.1 返回生成的图片
    """
    # 1. 获取参数
    # 1.1 获取前端携带的imageCodeId编号
    imageCodeId = request.args.get("imageCodeId")

    #2. 校验参数
    #2.1 imageCodeId编号是否有值
    if not imageCodeId:
        abort(404)
    #3. 逻辑处理
    #3.0 生成验证码图片&验证码图片的真实值
    name, text, image = captcha.generate_captcha()

    try:
        #3.1 使用imageCodeId编号作为key存储生成的图片验证码真实值
        redis_store.set("imagecode_%s" %imageCodeId, text, ex=constants.IMAGE_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.error(e)
        abort(500)

    #4. 返回值处理
    #4.1 返回生成的图片
    respose = make_response(image)
    respose.headers["Content-Type"] = "image/jpg"
    return respose
