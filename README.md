> 让兔兔可以收集群友的消息图片并统计emoji和火星图

- 兔兔在插件安装后，就会自动开始记录群友的聊天图片

> 使用插件

- 动图(gif)无论如何都会被视为Emoji
- 对于静态图，只有图片大小小于50K的图片才被视为Emoji
- 发送 `兔兔查看Emoji` 或 `兔兔查看高频图` 可以查看本群内最常被发送的前10张Emoji。

- 当用户发送一张大于50K的图片时，如果该图片在最近5小时内被其他群员发送过，则兔兔会回复一句 `[@该目标]，这张图x点x分已经水过了`

![水过了例子](https://raw.githubusercontent.com/hsyhhssyy/amiyabot-hsyhhssyy-emoji-stat/master/dup_image_example.jpg)

- 当用户撤回一张图片后，兔兔会发送 `撤回也没用哦，兔兔已经看见啦。` 。注意：该功能初始默认关闭。

> 管理插件

- 查看状态
    - 在群内发送 `兔兔查看图片记录状态` 可以查看各个功能的开启和关闭情况
    - 在群内发送 `兔兔查看水图王` 可以查看群内各个用户发图的数量和大小
    
    ![水图王例子](https://raw.githubusercontent.com/hsyhhssyy/amiyabot-hsyhhssyy-emoji-stat/master/user_stat.jpg)

- 群内管理命令
    - 管理员在群内发送 `兔兔停止收集Emoji` 就可以暂时停止对Emoji的收集
    - 管理员在群内发送 `兔兔开始收集Emoji` 就可以开始或者恢复对Emoji的收集

    - 管理员在群内发送 `兔兔关闭水过了功能` 就可以暂时停止兔兔对水过了图片的吐槽。
    - 管理员在群内发送 `兔兔开启水过了功能` 就可以开始或恢复兔兔对水过了图片的吐槽。

    - 管理员在群内发送 `兔兔关闭撤回捕捉` 就可以停止兔兔对撤回图片的捕捉。
    - 管理员在群内发送 `兔兔开启撤回捕捉` 就可以开始或恢复兔兔对撤回图片的捕捉。并且，此时兔兔会回复并提醒大家 `兔兔已经开始记录撤回的图片了，撤回图片会为管理员保存24小时哦。`

- 私聊管理命令
    - 管理员私聊兔兔发送 `查看撤回图片X分` 或  `兔兔查看撤回图片X` ，兔兔会将最近X分钟内撤回的图片私聊发送给你。X最多为24x60=1440分钟。更早的图片将无法查看。

    ![水过了例子](https://raw.githubusercontent.com/hsyhhssyy/amiyabot-hsyhhssyy-emoji-stat/master/recall_example.jpg)

    - 管理员私聊兔兔发送 `清理图片X天` 则插件会删除系统中缓存里X天以上的缓存图片，X为一个数字，最多不超过300。该功能会影响Emoji的统计，过老的Emoji会被删除和归零。

    - 管理员私聊兔兔发送 `清理图片XM` 则插件会删除系统中缓存里大小大于X MB的缓存图片，X为一个数字。该功能会影响Emoji的统计，过老的Emoji会被删除和归零。建议清理时，这个数字不低于10M，否则一些GIF图可能会被误删除

> 注意事项

- 警告
    - 警告：保存他人图片和聊天内容，有可能侵犯隐私，如果发生此行为，请您自行承担责任。
    - 警告：恶意收集他人消息可能会招致用户厌恶，进而导致玩家对bot或管理员的举报，请注意自行承担风险。
    - 警告：收集图片和Emoji会占用大量磁盘空间，网友可是会天天发的。使用的过程中，请时刻关注磁盘空间占用情况。

- 收集的图片保存在 `resource\emoji-stat\emoji\` 和 `resource\emoji-stat\image\` 下，必要时您可以手动清理。

- 监视撤回功能只在通过mirai控制的QQ群内才能有效，其他情况下相关的功能和指令均不会有任何效果和响应。

> 其他说明

- 本项目刚刚开发完成，测试的不一定足够充分，可能会遇到很多问题，如果在使用中遇到问题，请尽可能通过下面的反馈链接来反馈。
- 未来几个版本的更新

> [项目地址:Github](https://github.com/hsyhhssyy/amiyabot-hsyhhssyy-emoji-stat/)

> [遇到问题可以在这里反馈(Github)](https://github.com/hsyhhssyy/amiyabot-hsyhhssyy-emoji-stat/issues/new/)

> [如果上面的连接无法打开可以在这里反馈(Gitee)](https://gitee.com/hsyhhssyy/amiyabot-plugin-bug-report/issues/new)

> [Logo作者:Sesern老师](https://space.bilibili.com/305550122)

|  版本   | 变更  |
|  ----  | ----  |
| 1.0  | 初版登录商店 |
| 1.1  | 新增统计水图王功能 |
| 1.2  | 优化水图王功能的排版 |
