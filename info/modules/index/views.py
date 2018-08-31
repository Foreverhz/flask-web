from flask import g
from info.models import User, News, Category
from info.utils.response_code import RET
from . import index_bp
from flask import session, current_app, render_template, request, jsonify
from info import redis_store, models, constants
from info.utils.common import login_user_data


@index_bp.route('/news_list')
def get_news_list():
    """获取首页新闻列表的数据接口"""
    """
    1.获取参数
        1.1 cid分类id page当前页码（默认展示第一页） per_page当前页展示多少条数据（默认展示10条新闻）
    2.校验参数
        2.1 非空判断
        2.2 对数据类型进行校验判断
    3.逻辑处理
        3.3 根据上传参数进行数据库分页查询
        3.4 将数据转换成dict对象给前端使用
    4.返回值处理
    """
    #1.1 cid分类id page当前页码（默认展示第一页） per_page当前页展示多少条数据（默认展示10条新闻）
    cid = request.args.get("cid")
    page = request.args.get("page", 1)
    per_page = request.args.get("per_page", constants.HOME_PAGE_MAX_NEWS)

    #2.1 非空判断
    if not all([cid, page, per_page]):
        return jsonify(errno=RET.DATAERR, errmsg="参数不足")
    #2.2 对数据类型进行校验判断
    try:
        cid = int(cid)
        page = int(page)
        per_page = int(per_page)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg="数据类型错误")

    # 最新的新闻 不需要根据cid来查询只需要根据创建时间来查询
    filters = [News.status == 0]
    if cid != 1:
        # 将查询条件添加到filter列表中
        # ==底层是重写过的 News.category_id == cid是一个查询条件
        filters.append(News.category_id == cid)

    try:
        #3.3 根据上传参数进行数据库分页查询
        paginate = News.query.filter(*filters).order_by(News.create_time.desc()).paginate(page, per_page, False)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询新闻列表数据异常")

    # 当前页码所有数据
    items = paginate.items
    # 当前页码
    current_page = paginate.page
    # 总页数
    total_page = paginate.pages

    #3.4 将数据转换成dict对象给前端使用
    newsList = []
    # 遍历items模型列表获取个每一个模型进而转换成字典添加在newsList中
    for news in items if items else None:
        newsList.append(news.to_dict())
    # 组织数据
    data = {
        "newsList": newsList,
        "current_page": current_page,
        "total_page": total_page
    }
    #4.组织响应对象
    return jsonify(errno=RET.OK, errmsg="查询新闻list数据成功", data=data)



#2. 使用蓝图对象
# 127.0.0.1:5000/index/

@index_bp.route('/')
@login_user_data
def index():
    #------- 1.查询用户信息将用户信息通过模板带回进行展示--------
    user = g.user
    # if user:
    #     return user.to_dict()
    # else:
    #     return None
    # 3.经用户模型对象转换成用户的字典对象

    #------- 2.查询新闻的点击排行数据进行展示--------
    try:
        news_model_list = News.query.order_by(News.clicks.desc()).limit(constants.CLICK_RANK_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)
        # 切记不需要return


    # 将模型列表转换成字典列表
    news_dict_list = []
    for news in news_model_list if news_model_list else []:
        # 将新闻模型对象转成成字典对象添加到news_dict_list列表中
        news_dict_list.append(news.to_dict())

    # ------- 3.查询新闻的分类数据进行展示--------
    categories = []
    try:
        categories = Category.query.all()
    except Exception as e:
        current_app.logger.error(e)

    # 对象模型列表转字典列表
    category_dict_list = []
    for category in categories if  categories else []:
        # 将category对象转换成字典添加到列表中
        category_dict_list.append(category.to_dict())

    # 构建响应数据
    data = {
        "user_info": user.to_dict() if user else None,
        "newsClicksList": news_dict_list,
        "categories": category_dict_list
    }

    return render_template("index.html", data=data)


#返回web的头像图标
@index_bp.route('/favicon.ico')
def favicon():
    """返回项目图标"""
    # send_static_file: 将static中的静态文件发送给浏览器
    return current_app.send_static_file("news/favicon.ico")