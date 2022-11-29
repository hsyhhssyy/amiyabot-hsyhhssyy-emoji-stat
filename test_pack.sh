#!/bin/sh

zip -q -r amiyabot-hsyhhssyy-emoji-stat-1.2.zip *
rm -rf ../../amiya-bot-v6/plugins/amiyabot-hsyhhssyy-emoji-stat-*
mv amiyabot-hsyhhssyy-emoji-stat-*.zip ../../amiya-bot-v6/plugins/
docker restart amiya-bot 