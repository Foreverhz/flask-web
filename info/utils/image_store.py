import qiniu
from flask import current_app

access_key = "W0oGRaBkAhrcppAbz6Nc8-q5EcXfL5vLRashY4SI"
secret_key = "tsYCBckepW4CqW0uHb9RdfDMXRDOTEpYecJAMItL"


def qiniu_image_store(data):
    # 创建鉴权对象
    q = qiniu.Auth(access_key, secret_key)
    # key 上传的图片名称 不指明让七牛云给你生成一个唯一的图片名称
    # key = 'hello'
    bucket_name = "python-ihome"
    token = q.upload_token(bucket_name)
    try:
        ret, info = qiniu.put_data(token, None, data)
        if ret is not None and info.status_code == 200:
            # print(ret)
            print('All is OK-------------')
            # print(info)
            # 返回图片名称
            return ret["key"]
        else:
            print(info)  # error message in info
    except Exception as e:
        current_app.logger.error(e)
        # 自己封装的工具类给被人用的时候需要将异常抛出不能私自解决
        raise e


if __name__ == '__main__':
    file = input("请输入图片路径:")
    with open(file, "rb") as f:
        qiniu_image_store(f.read())