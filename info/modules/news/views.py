from flask import abort, jsonify
from flask import current_app
from flask import g
from flask import render_template
from flask import request
from flask import session
from info import constants, db
from info.models import News, User, Comment, CommentLike
from info.utils.response_code import RET
from . import news_bp
from info.utils.common import login_user_data


@news_bp.route('/comment_like', methods=["POST"])
@login_user_data
def comment_like():
    """评论的点赞、取消点赞接口"""
    """
       1.获取参数
           1.1 用户对象 新闻id comment_id评论的id，action:(点赞、取消点赞)
       2.校验参数
           2.1 非空判断
           2.2 用户是否登录判断
           2.3 action in ["add", "remove"]
       3.逻辑处理
          3.1 根据comment_id查询评论对象
          3.2 根据action进行点赞、取消点赞的操作
          3.3 新建comment_like模型对象 将其属性赋值保存到数据库
       4.返回值处理
       """
    #1.1 用户对象 新闻id comment_id评论的id，action:(点赞、取消点赞)
    params_dict = request.json
    news_id = params_dict.get("news_id")
    comment_id = params_dict.get("comment_id")
    action = params_dict.get("action")
    user = g.user

    #2.1 非空判断
    if not all([news_id, comment_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    #2.2 用户是否登录判断
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    #2.3 action in ["add", "remove"]
    if action not in ["add", "remove"]:
        return jsonify(errno=RET.PARAMERR, errmsg="action参数错误")

    #3.1 根据comment_id查询评论对象
    comment = None
    try:
        comment = Comment.query.get(comment_id)
    except Exception as e:
        return jsonify(errno=RET.DBERR, errmsg="查询评论对象异常")

    if not comment:
        return jsonify(errno=RET.NODATA, errmsg="评论不存在")

    #3.2 根据action进行点赞、取消点赞的操作
    if action == "add":
        # 点赞
        try:
            # 如果存在comment_like对象表示该用户对该评论点过赞
            comment_like = CommentLike.query.filter(CommentLike.comment_id==comment_id,
                                    CommentLike.user_id==user.id).first()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询comment_like异常")

        if not comment_like:
            # 1.创建CommentLike对象(维护用户和评论的多对多的第三张表的关系)
            comment_like = CommentLike()
            comment_like.user_id = user.id
            comment_like.comment_id = comment_id
            # 将模型对象添加到数据库会话对象中
            db.session.add(comment_like)

            #2.评论模型对象中like_count属性赋值 点赞数量加一
            comment.like_count += 1
    else:
        # 取消点赞
        # 如果存在comment_like对象表示该用户对该评论点过赞
        try:
            # 如果存在comment_like对象表示该用户对该评论点过赞
            comment_like = CommentLike.query.filter(CommentLike.comment_id == comment_id,
                                                    CommentLike.user_id == user.id).first()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询comment_like异常")

        if comment_like:
            # 用户取消点赞删除中间表的关系
            db.session.delete(comment_like)
            # 2.评论模型对象中like_count属性赋值 取消点赞数量减一
            comment.like_count -= 1

    #3.3 新建comment_like模型对象 将其属性赋值保存到数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存comment_like模型对象异常")

    #4.组织响应数据
    return jsonify(errno=RET.OK, errmsg="OK")


@news_bp.route('/news_comment', methods=["POST"])
@login_user_data
def news_comment():
    """新闻评论接口 （主评论、子评论）"""
    """
    1.获取参数
        1.1 用户对象 新闻id comment评论内容，评论的parent_id
    2.校验参数
        2.1 非空判断
        2.2 用户是否登录判断
    3.逻辑处理
        3.1 根据news_id查询该新闻是否存在
        3.2 创建评论对象 给各个属性赋值
        3.3 parent_id是否有值，有值：子评论 没有值：主评论
        3.4 将评论对象保存到数据
    4.返回值处理
    """
    # 1.1 用户对象 新闻id comment评论内容，评论的parent_id
    params_dict = request.json
    news_id = params_dict.get("news_id")
    comment = params_dict.get("comment")
    # 根据前端需求来传递的
    parent_id = params_dict.get("parent_id")

    user = g.user
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    #2.1 非空判断
    if not all([news_id, comment]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    #3.1 根据news_id查询该新闻是否存在
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询新闻数据异常")

    if not news:
        return jsonify(errno=RET.NODATA, errmsg="新闻不存在")

    #3.2 创建评论对象 给各个属性赋值
    comment_obj = Comment()
    comment_obj.user_id = user.id
    comment_obj.news_id = news_id
    comment_obj.content = comment
    # 3.3 parent_id是否有值，有值：子评论 没有值：主评论
    if parent_id:
        comment_obj.parent_id = parent_id

    #3.4 将评论对象保存到数据
    try:
        db.session.add(comment_obj)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 回滚
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="评论对象保存到数据库异常")

    # 4. 组织响应对象
    return jsonify(errno=RET.OK, errmsg="评论成功", data=comment_obj.to_dict())


# /news/news_collect POST
@news_bp.route('/news_collect', methods=["POST"])
@login_user_data
def news_collect():
    """新闻收藏、取消收藏接口"""
    """
    1.获取参数
        1.1 用户对象 新闻id action(收藏、取消收藏)
    2.校验参数
        2.1 非空判断
        2.2 action处于["collect", "cancel_collect"]
    3.逻辑处理
        3.1 根据新闻id查询出该新闻
        3.2 收藏：将新闻添加到user.collection_news列表中
        3.3 取消收藏：将新闻从user.collection_news列表移除
    4.返回值处理
    """

    # 1.1 用户对象 新闻id action(收藏、取消收藏)
    params_dict = request.json
    news_id = params_dict.get("news_id")
    action = params_dict.get("action")
    user = g.user

    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    #2.1 非空判断
    if not all([news_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    #2.2 action处于["collect", "cancel_collect"]
    if action not in ["collect", "cancel_collect"]:
        return jsonify(errno=RET.PARAMERR, errmsg="参数填写错误")

    #3.1 根据新闻id查询出该新闻
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询新闻数据异常")

    if not news:
        return jsonify(errno=RET.NODATA, errmsg="新闻不存在")

    #3.2 收藏：将新闻添加到user.collection_news列表中
    if action == "collect":
        user.collection_news.append(news)
    else:
        #3.3 取消收藏：将新闻从user.collection_news列表移除
        user.collection_news.remove(news)

    # 3.3 你可以选择提交修改到数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存收藏数据异常")



    # 4.返回值处理
    return jsonify(errno=RET.OK, errmsg="OK")


# 127.0.0.1:5000/news/12
# 点击那条新闻需要将改新闻的id传过来方便查询
@news_bp.route('/<int:news_id>')
@login_user_data
def news_detail(news_id):
    """新闻详情首页接口"""
    # ------- 1.查询用户信息将用户信息通过模板带回进行展示--------
    user = g.user

    # 1. 如果用户登录成功就能够获取用户的id
    # user_id = session.get("user_id")
    # user = None
    # # 2. 根据用户id查询用户所有的数据
    # try:
    #     if user_id:
    #         user = User.query.get(user_id)
    # except Exception as e:
    #     current_app.logger.error(e)
        # 切记不需要return

    # if user:
    #     return user.to_dict()
    # else:
    #     return None
    # 3.经用户模型对象转换成用户的字典对象

    # ------- 2.查询新闻的点击排行数据进行展示--------
    try:
        news_model_list = News.query.order_by(News.clicks.desc()).limit(constants.CLICK_RANK_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)

    # 将模型列表转换成字典列表
    news_dict_list = []
    for news in news_model_list if news_model_list else []:
        # 将新闻模型对象转成成字典对象添加到news_dict_list列表中
        news_dict_list.append(news.to_dict())

    # ------- 3.查询新闻的详情内容数据进行展示--------
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        abort(404)

    if not news:
        abort(404)

    # 注意： 浏览量自增
    news.clicks += 1

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 回滚
        db.session.rollback()
        abort(404)

    # ------- 4.查询用户是否收藏过该新闻--------
    # False: 未收藏 True: 收藏过了
    is_collected = False
    is_followed = False

    # # 1.判断用户是否登录
    # if not user:
    #     abort(404)

    # 只有在用户处于登录状态才去判断用户是否收藏了该新闻
    if user:
        # 2.判断新闻对象是否在收藏列表
        if news in user.collection_news if user.collection_news else []:
            # 已经收藏了该新闻
            is_collected = True

    # 用户已经登录 同时 进入详情页面的作者存在
    # user: 当前登录用户  news.user: 作者
    if user and news.user:
        # news.user in user.followed :作者在用的偶像列表内 （登录的用户是这个作者的粉丝，表示关注过）
        # user in news.user.followers :当前登录的用户在新闻作者的粉丝列表中
        if user in news.user.followers:
            is_followed = True

    # ------- 5.查询新闻的评论的列表数据--------
    comments = []

    try:
        # 查询对应新闻的评论列表 [comment1, comment2....]
        comments = Comment.query.filter(Comment.news_id == news_id).order_by(Comment.create_time.desc()).all()
    except Exception as e:
        current_app.logger.error(e)

    # ------- 6.查询当前用户对该新闻的那几条评论点过赞--------
    # 模型列表转字典列表
    comment_dict_list = []
    commentlike_id_list = []
    # 只有用户登录成功后才能去查看当前用户的点过赞的评论
    if user:
        #1. 查询出当前新闻的所有评论，取得所有评论的id —>  list[1,2,3,4,5,6]
        comment_id_list = [comment.id for comment in comments]

        #2.再通过评论点赞模型(CommentLike)查询当前用户点赞了那几条评论  —>[模型1,模型2...]
        # 过滤出该用户点过那几条评论的赞
        commentlike_model_list = CommentLike.query.filter(CommentLike.comment_id.in_(comment_id_list),
                                                          CommentLike.user_id == user.id
                                                          ).all()
        #3. comment_like.comment_id通过上一步的模型列表，获取所以点赞过的评论id
        commentlike_id_list = [commentlike.comment_id for commentlike in commentlike_model_list]


    # 遍历模型对象列表
    for comment in comments if comments else []:
        # 模型对象转成字典
        comment_dict = comment.to_dict()
        comment_dict["is_like"] = False
        # 过滤那条评论的是被该用户点过赞的
        # [1,2,3,4,5,6] --> [1,3,5]
        if comment.id in commentlike_id_list:
            comment_dict["is_like"] = True

        comment_dict_list.append(comment_dict)

    # 组织响应数据
    data = {
        "user_info": user.to_dict() if user else None,
        "newsClicksList": news_dict_list,
        "news": news.to_dict() if news else None,
        "is_collected": is_collected,
        "is_followed": is_followed,
        "comments": comment_dict_list
    }

    return render_template("news/detail.html", data=data)