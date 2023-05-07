import os
import time
from io import BytesIO

import dhash
from PIL import Image
from amiyabot import Message, Chain, log, PluginInstance, Event
from amiyabot.database import *
from amiyabot.network.download import download_async
from core.database.bot import DisabledFunction

from .imghdr import what

curr_dir = os.path.dirname(__file__)
max_disc = 5
max_static_image_threhold = 50 * 1024
db = connect_database(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')


class EmojiStatBaseModel(ModelClass):
    class Meta:
        database = db


@table
class EmojiStat(EmojiStatBaseModel):
    class Meta:
        table_name = 'EMOJI_STAT'
        primary_key = CompositeKey('IMAGE_HASH', 'CHANNEL_ID')

    IMAGE_HASH: str = TextField(null=False)
    MESSAGE_ID: str = TextField(null=False)
    SEND_COUNT: int = IntegerField(null=False)
    SEND_TIME: int = IntegerField(null=False)
    CHANNEL_ID: str = TextField(null=False)
    IMAGE_TYPE: str = TextField(null=False)
    IMAGE_CAT: str = TextField(null=False)
    LAST_SENDER: str = TextField(null=False)


@table
class RecallImage(EmojiStatBaseModel):
    class Meta:
        table_name = 'RECALL_IMAGE'
        primary_key = CompositeKey('IMAGE_HASH', 'MESSAGE_ID')

    IMAGE_HASH: str = TextField(null=False)
    MESSAGE_ID: str = TextField(null=False)
    RECALL_TIME: int = IntegerField(null=False)
    CHANNEL_ID: str = TextField(null=False)
    CHANNEL_NAME: str = TextField(null=True)
    IMAGE_TYPE: str = TextField(null=False)
    IMAGE_CAT: str = TextField(null=False)
    SENDER: str = TextField(null=False)


@table
class PluginConfig(EmojiStatBaseModel):
    class Meta:
        table_name = 'PLUGIN_CONFIG'
        primary_key = CompositeKey('FUNCTION_NAME', 'CHANNEL_ID')

    FUNCTION_NAME: str = TextField(null=False)
    CURRENT_STATE: str = TextField(null=False)
    CHANNEL_ID: str = TextField(null=False)


@table
class UserStat(EmojiStatBaseModel):
    class Meta:
        table_name = 'USER_STAT'
        primary_key = CompositeKey('USER_ID', 'CHANNEL_ID')

    USER_ID: str = TextField(null=False)
    USER_NICKNAME: str = TextField(null=False)
    CHANNEL_ID: str = TextField(null=False)
    IMAGE_COUNT: int = IntegerField(null=False)
    IMAGE_SIZE: int = IntegerField(null=False)
    EMOJI_COUNT: int = IntegerField(null=False)
    EMOJI_SIZE: int = IntegerField(null=False)


class EmojiStatPluginInstance(PluginInstance):
    def install(self):

        if not os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji'):
            os.makedirs(f'{curr_dir}/../../resource/emoji-stat/emoji')

        if not os.path.exists(f'{curr_dir}/../../resource/emoji-stat/image'):
            os.makedirs(f'{curr_dir}/../../resource/emoji-stat/image')

        config = PluginConfig.get_or_none(PluginConfig.FUNCTION_NAME == 'emoji_collect_enabled')
        if config is None:
            PluginConfig.create(FUNCTION_NAME='emoji_collect_enabled', CURRENT_STATE='True', CHANNEL_ID='ALL')


bot = EmojiStatPluginInstance(
    name='图片记录员',
    version='1.6',
    plugin_id='amiyabot-hsyhhssyy-emoji-stat',
    plugin_type='',
    description='让兔兔可以收集群友的消息图片，统计常用emoji，和在群友火星了的时候提醒他们。\n1.3版本修复了可执行文件部署时报错找不到img-hdr的问题',
    document=f'{curr_dir}/README.md'
)


async def get_config(config_name, channel_id, default_value):
    rows = PluginConfig.select(PluginConfig.CURRENT_STATE).where(PluginConfig.FUNCTION_NAME == config_name,
                                                                 PluginConfig.CHANNEL_ID == channel_id)
    if len(rows) <= 0:
        # 写入该值
        if default_value:
            write_value = 'True'
        else:
            write_value = 'False'

        PluginConfig.create(FUNCTION_NAME=config_name, CURRENT_STATE=write_value, CHANNEL_ID=channel_id)
        log.info(f"写入配置初始值{config_name} {write_value} {channel_id}")
        return default_value
    else:
        return rows[0].CURRENT_STATE == 'True'


async def set_config(config_name, channel_id, value):
    if value:
        write_value = 'True'
    else:
        write_value = 'False'

    rows = PluginConfig.select(PluginConfig.CURRENT_STATE).where(PluginConfig.FUNCTION_NAME == config_name,
                                                                 PluginConfig.CHANNEL_ID == channel_id)
    if len(rows) <= 0:
        # 写入该值
        PluginConfig.create(FUNCTION_NAME=config_name, CURRENT_STATE=write_value, CHANNEL_ID=channel_id)
    else:
        # 更新该值
        PluginConfig.update(CURRENT_STATE=write_value).where(PluginConfig.FUNCTION_NAME == config_name,
                                                             PluginConfig.CHANNEL_ID == channel_id).execute()


async def any_talk(data: Message):
    disabled = DisabledFunction.get_or_none(
        function_id='amiyabot-hsyhhssyy-emoji-stat',
        channel_id=data.channel_id
    )
    if disabled:
        return False, 0

    channel_id = data.channel_id
    emoji_collect_enabled = await get_config('emoji_collect_enabled', channel_id, True)
    martian_detect_enabled = await get_config('martian_detect_enabled', channel_id, True)
    recall_spy_enabled = await get_config('recall_spy_enabled', channel_id, False)

    # 计算所有的Hash
    for image_item in data.image:
        imgBytes = await download_async(image_item)
        if imgBytes:
            image = BytesIO(imgBytes)
            try:
                image_type = what(None, imgBytes)

                if image_type is None:
                    image_type = "Unknown"

                length = image.getbuffer().nbytes

                if length > max_static_image_threhold and image_type != 'gif':
                    # 判定为普通图片
                    if not martian_detect_enabled and not recall_spy_enabled:
                        continue

                    hash_value = dhash.dhash_int(Image.open(image), 16)
                    file_path = f'{curr_dir}/../../resource/emoji-stat/image/{hash_value}'

                    with open(file_path, mode='wb+') as src:
                        src.write(imgBytes)

                    await check_image(hash_value, file_path, image_type, data)
                else:

                    if not emoji_collect_enabled:
                        continue

                    hash_value = hashlib.md5(imgBytes).hexdigest()
                    file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{hash_value}'

                    with open(file_path, mode='wb+') as src:
                        src.write(imgBytes)

                    await check_emoji(hash_value, file_path, image_type, data)

            except OSError:
                continue

    return False, 0


async def check_emoji(hash_value, file_path, image_type, data):
    # emoji使用文件hash而不是图像灰度hash

    user_id = data.user_id
    channel_id = data.channel_id
    now = time.time()

    emoji_collect_enabled = await get_config('emoji_collect_enabled', channel_id, True)
    if not emoji_collect_enabled:
        return

    if not UserStat.get_or_none(UserStat.USER_ID == user_id, UserStat.CHANNEL_ID == channel_id):
        UserStat.create(USER_ID=user_id, USER_NICKNAME=data.nickname, CHANNEL_ID=channel_id, IMAGE_COUNT=0,
                        IMAGE_SIZE=0, EMOJI_COUNT=0, EMOJI_SIZE=0)

    if os.path.exists(file_path):
        stats = os.stat(file_path)
        total_size = stats.st_size
    else:
        total_size = 0
    UserStat.update(EMOJI_COUNT=UserStat.EMOJI_COUNT + 1, EMOJI_SIZE=UserStat.EMOJI_SIZE + total_size,
                    USER_NICKNAME=data.nickname).where(UserStat.USER_ID == user_id,
                                                       UserStat.CHANNEL_ID == channel_id).execute()

    all_rows = EmojiStat.select(EmojiStat.SEND_TIME).where(EmojiStat.IMAGE_HASH == f'{hash_value}',
                                                           EmojiStat.CHANNEL_ID == channel_id,
                                                           EmojiStat.IMAGE_CAT == 'EMOJI')
    if len(all_rows) > 0:
        EmojiStat.update(SEND_COUNT=EmojiStat.SEND_COUNT + 1, SEND_TIME=now, LAST_SENDER=user_id,
                         MESSAGE_ID=data.message_id).where(EmojiStat.IMAGE_HASH == f'{hash_value}',
                                                           EmojiStat.CHANNEL_ID == channel_id,
                                                           EmojiStat.IMAGE_CAT == 'EMOJI').execute()
    else:
        EmojiStat.create(IMAGE_HASH=f'{hash_value}', SEND_TIME=now, SEND_COUNT=1, LAST_SENDER=user_id,
                         CHANNEL_ID=channel_id, IMAGE_TYPE=image_type, IMAGE_CAT='EMOJI',
                         MESSAGE_ID=data.message_id)


async def check_image(hash_value, file_path, image_type, data):
    user_id = data.user_id
    channel_id = data.channel_id
    now = time.time()
    delta = now - 5 * 60 * 60

    if not UserStat.get_or_none(UserStat.USER_ID == user_id, UserStat.CHANNEL_ID == channel_id):
        UserStat.create(USER_ID=user_id, USER_NICKNAME=data.nickname, CHANNEL_ID=channel_id, IMAGE_COUNT=0,
                        IMAGE_SIZE=0, EMOJI_COUNT=0, EMOJI_SIZE=0)

    if os.path.exists(file_path):
        stats = os.stat(file_path)
        total_size = stats.st_size
    else:
        total_size = 0
    UserStat.update(IMAGE_COUNT=UserStat.IMAGE_COUNT + 1, IMAGE_SIZE=UserStat.IMAGE_SIZE + total_size,
                    USER_NICKNAME=data.nickname).where(UserStat.USER_ID == user_id,
                                                       UserStat.CHANNEL_ID == channel_id).execute()

    martian_detect_enabled = await get_config('martian_detect_enabled', channel_id, True)
    if not martian_detect_enabled:
        return

    all_rows = EmojiStat.select(EmojiStat.SEND_TIME).where(EmojiStat.IMAGE_HASH == f'{hash_value}',
                                                           EmojiStat.CHANNEL_ID == channel_id,
                                                           EmojiStat.IMAGE_CAT == 'IMAGE')

    if len(all_rows) > 0:
        l_time = all_rows[0].SEND_TIME

        if l_time > delta:
            await data.send(
                Chain(data).text(f'博士，这张图已经在{time.strftime("%H:%M:%S", time.localtime(l_time))}水过了。'))

        EmojiStat.update(SEND_COUNT=EmojiStat.SEND_COUNT + 1, SEND_TIME=now, LAST_SENDER=user_id,
                         MESSAGE_ID=data.message_id).where(EmojiStat.IMAGE_HASH == f'{hash_value}',
                                                           EmojiStat.CHANNEL_ID == channel_id,
                                                           EmojiStat.IMAGE_CAT == 'IMAGE').execute()
    else:
        # 进行hash比较
        c = EmojiStat.select(EmojiStat.IMAGE_HASH, EmojiStat.SEND_TIME).where(EmojiStat.SEND_TIME > delta,
                                                                              EmojiStat.CHANNEL_ID == channel_id,
                                                                              EmojiStat.IMAGE_CAT == 'IMAGE')
        for row_ in c:
            compare_hash = int(row_.IMAGE_HASH, 16)
            diff = dhash.get_num_bits_different(hash_value, compare_hash)
            if diff <= max_disc:
                await data.send(
                    Chain(data).text(
                        f'博士，这张图已经在{time.strftime("%H:%M:%S", time.localtime(row_.SEND_TIME))}水过了。'))
                break

        EmojiStat.create(IMAGE_HASH=f'{hash_value}', SEND_TIME=now, SEND_COUNT=1, LAST_SENDER=user_id,
                         CHANNEL_ID=channel_id, IMAGE_TYPE=image_type, IMAGE_CAT='IMAGE',
                         MESSAGE_ID=data.message_id)


# noinspection PyUnusedLocal
@bot.on_message(verify=any_talk, check_prefix=False)
async def _(data: Message):
    return


@bot.on_event('GroupRecallEvent')
async def _(event: Event, instance):
    data = event.data
    message_id = data['messageId']
    group = data['group']

    log.info(f'recall message: {message_id} {group} ')

    recall_spy_enabled = await get_config('recall_spy_enabled', group["id"], False)
    if not recall_spy_enabled:
        return

    now = time.time()

    c = EmojiStat.select(EmojiStat.IMAGE_HASH, EmojiStat.CHANNEL_ID, EmojiStat.IMAGE_TYPE, EmojiStat.IMAGE_CAT,
                         EmojiStat.LAST_SENDER).where(EmojiStat.MESSAGE_ID == message_id)

    user_id = None
    row = None

    for row in c:
        # 写入Recall表
        RecallImage.create(IMAGE_HASH=f'{row.IMAGE_HASH}', MESSAGE_ID=message_id, RECALL_TIME=now,
                           CHANNEL_ID=row.CHANNEL_ID, IMAGE_TYPE=row.IMAGE_TYPE, IMAGE_CAT=row.IMAGE_CAT,
                           SENDER=row.LAST_SENDER, CHANNEL_NAME=group["name"])
        user_id = row.LAST_SENDER

    if user_id:
        await instance.send_message(Chain().at(user_id).text(f'博士，撤回也没用哦，兔兔已经看见啦。'),
                                    channel_id=row.CHANNEL_ID)


@bot.on_message(keywords=['查看Emoji', '查看高频图', '查询Emoji', '查询高频图'], level=5)
async def _(data: Message):
    channel_id = data.channel_id

    emoji_collect_enabled = await get_config('emoji_collect_enabled', channel_id, True)

    if not emoji_collect_enabled:
        return

    c = EmojiStat.select(EmojiStat.IMAGE_HASH, EmojiStat.SEND_COUNT, EmojiStat.IMAGE_TYPE, EmojiStat.IMAGE_CAT).where(
        EmojiStat.CHANNEL_ID == channel_id, EmojiStat.IMAGE_CAT == 'EMOJI').order_by(EmojiStat.SEND_COUNT.desc()).limit(
        10)

    image_order = 0
    for row in c:
        image_order += 1
        file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{row.IMAGE_HASH}'
        send_count = row.SEND_COUNT
        await data.send(
            Chain(data, at=False).text(f'博士，群内Emoji第{image_order}名被发送过{send_count}次，它是：').image(file_path))


@bot.on_message(keywords=['水图王'], level=5)
async def _(data: Message):
    channel_id = data.channel_id

    c = UserStat.select(UserStat.USER_ID, UserStat.USER_NICKNAME, UserStat.EMOJI_COUNT, UserStat.IMAGE_COUNT).where(
        UserStat.CHANNEL_ID == channel_id).order_by((UserStat.IMAGE_COUNT + UserStat.EMOJI_COUNT).desc()).limit(5)

    image_order = 0
    message_to_send = '发送图片数量的排名如下：\n'

    for row in c:
        image_order += 1
        message_to_send = message_to_send + f'第{image_order}名："{row.USER_NICKNAME}"博士\t' \
                                            f'发送过{row.EMOJI_COUNT + row.IMAGE_COUNT}张图片。\n'

    await data.send(Chain(data, at=False).text(message_to_send))

    c = UserStat.select(UserStat.USER_ID, UserStat.USER_NICKNAME, UserStat.EMOJI_SIZE, UserStat.IMAGE_SIZE).where(
        UserStat.CHANNEL_ID == channel_id).order_by((UserStat.IMAGE_SIZE + UserStat.EMOJI_SIZE).desc()).limit(5)

    image_order = 0
    message_to_send = '发送图片大小的排名如下：\n'

    for row in c:
        image_order += 1

        size = row.EMOJI_SIZE + row.IMAGE_SIZE

        size_text = f'{size}Byte'
        if size > 1024 * 1024 * 1024:
            size_text = f'{int(size / 1024 / 1024 / 1024)}GB'
        elif size > 1024 * 1024:
            size_text = f'{int(size / 1024 / 1024)}MB'
        elif size > 1024:
            size_text = f'{int(size / 1024)}KB'

        message_to_send = message_to_send + f'第{image_order}名："{row.USER_NICKNAME}"博士\t发送过{size_text}的图片。\n'

    await data.send(Chain(data, at=False).text(message_to_send))


@bot.on_message(keywords=['查看撤回图片'], check_prefix=False, direct_only=True)
async def _(data: Message):
    match = re.search(r'查看撤回图片(\d*?)分', data.text_digits)
    if match:
        minute_delta = int(match.group(1))
    else:
        return Chain(data).text(f'博士，请发送 查看撤回图片X分 来指定查看的时间哦。')

    # 回溯时间，单位为秒
    now = time.time()
    if minute_delta > 24 * 60:
        minute_delta = 24 * 60
    time_delta = now - minute_delta * 60

    c = RecallImage.select(RecallImage.IMAGE_HASH, RecallImage.CHANNEL_ID, RecallImage.SENDER, RecallImage.RECALL_TIME,
                           RecallImage.IMAGE_CAT).where(RecallImage.RECALL_TIME > time_delta)
    image_count = 0
    for row in c:
        if row.IMAGE_CAT == 'EMOJI':
            file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{row.IMAGE_HASH}'
        else:
            file_path = f'{curr_dir}/../../resource/emoji-stat/image/{row.IMAGE_HASH}'

        image_count += 1
        await data.send(Chain(data).text(
            f'频道{row.CHANNEL_ID}的用户{row.SENDER}在{time.strftime("%H:%M:%S", time.localtime(row.RECALL_TIME))}撤回了如'
            f'下图片:').image(file_path))

    return Chain(data).text(f'撤回图片列出完毕，在{minute_delta}分内共计{image_count}张图片。')


@bot.on_message(keywords=['关闭收集Emoji', '停止收集Emoji'], level=5)
async def _(data: Message):
    channel_id = data.channel_id
    await set_config('emoji_collect_enabled', channel_id, False)

    return Chain(data).text(f'博士，兔兔现在停止收集Emoji啦。')


@bot.on_message(keywords=['开始收集Emoji', '打开收集Emoji', '开启收集Emoji'], level=5)
async def _(data: Message):
    channel_id = data.channel_id
    await set_config('emoji_collect_enabled', channel_id, True)

    return Chain(data).text(f'博士，兔兔现在开始收集Emoji啦。')


@bot.on_message(keywords=['关闭水过了', '停止水过了'], level=5)
async def _(data: Message):
    channel_id = data.channel_id
    await set_config('martian_detect_enabled', channel_id, False)

    return Chain(data).text(f'博士，兔兔现在不再关心大家消息是不是灵通啦。')


@bot.on_message(keywords=['开启水过了', '打开水过了'], level=5)
async def _(data: Message):
    channel_id = data.channel_id
    await set_config('martian_detect_enabled', channel_id, True)

    return Chain(data).text(f'博士，兔兔现在要看看谁消息不够灵通啦。')


@bot.on_message(keywords=['关闭撤回', '停止撤回'], level=5)
async def _(data: Message):
    channel_id = data.channel_id
    await set_config('recall_spy_enabled', channel_id, False)

    return Chain(data).text(f'博士，兔兔现在不再记录大家撤回的图片了。')


@bot.on_message(keywords=['开启撤回', '打开撤回'], level=5)
async def _(data: Message):
    channel_id = data.channel_id
    await set_config('recall_spy_enabled', channel_id, True)

    return Chain(data).text(f'博士，兔兔已经开始记录撤回的图片了，撤回图片会为管理员保存24小时哦。')


@bot.on_message(keywords=['查看图片记录状态'], level=10)
async def _(data: Message):
    channel_id = data.channel_id

    martian_detect_enabled = await get_config('martian_detect_enabled', channel_id, True)
    emoji_collect_enabled = await get_config('emoji_collect_enabled', channel_id, True)
    recall_spy_enabled = await get_config('recall_spy_enabled', channel_id, False)

    return Chain(data).text(
        f'博士，兔兔当前的状态是:\nEmoji统计：{"打开" if emoji_collect_enabled == True else "关闭"}\n水过了检测：'
        f'{"打开" if martian_detect_enabled == True else "关闭"}\n撤回记录：'
        f'{"打开" if recall_spy_enabled == True else "关闭"}')


@bot.on_message(keywords=['清理图片'], check_prefix=False, direct_only=True)
async def _(data: Message):
    match = re.search(r'清理图片(\d*?)天', data.text_digits)
    if match:
        date_delta = int(match.group(1))
    else:
        return Chain(data).text(f'博士，请发送 清理图片X天 来指定清理的天数哦。')

    now = time.time()
    delta = now - date_delta * 24 * 3600

    image_to_delete = []
    c = EmojiStat.select(EmojiStat.IMAGE_HASH, EmojiStat.IMAGE_CAT).where(EmojiStat.SEND_TIME < delta)

    for row in c:
        # 写入Recall表
        image_to_delete.append([row.IMAGE_HASH, row.IMAGE_CAT])

    total_size = 0
    total_count = 0

    for image_info in image_to_delete:
        # 删掉数据库记录
        EmojiStat.delete().where(EmojiStat.IMAGE_HASH == image_info[0]).execute()
        RecallImage.delete().where(RecallImage.IMAGE_HASH == image_info[0]).execute()
        # 删掉图片本身
        if image_info[1] == 'IMAGE':
            file_path = f'{curr_dir}/../../resource/emoji-stat/image/{image_info[0]}'
        else:
            file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{image_info[0]}'

        if os.path.exists(file_path):
            stats = os.stat(file_path)
            total_size += stats.st_size
            total_count += 1
            os.remove(file_path)

    return Chain(data).text(
        f'博士，兔兔清理了{date_delta}天内的图片，共计{total_count}张，共计大约{int(total_size / 1024 / 1024)}MB。')
