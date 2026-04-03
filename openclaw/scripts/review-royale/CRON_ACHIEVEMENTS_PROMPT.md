# Review Royale Achievement Notification Cron

You check for new achievements and post notifications to Discord.

## Steps

1. Query the Review Royale API for pending achievement notifications:
   ```
   curl -s http://localhost:3456/api/achievements/pending
   ```
2. If empty or error, reply "NO_ACHIEVEMENTS"
3. For each new achievement, send a message to #lodestar-developer (channel 1197575814494035968):
   ```
   🏆 **Achievement Unlocked!**
   
   [emoji] **[username]** earned **[achievement name]**!
   _[description]_
   ```
4. After posting, mark achievements as notified:
   ```
   curl -s -X POST "http://localhost:3456/api/achievements/[user_id]/[achievement_id]/notify"
   ```
5. Reply "ACHIEVEMENTS_POSTED: [count]" or "NO_ACHIEVEMENTS"

## Rules
- Post max 5 achievements per run to avoid spam
- Group multiple achievements for the same user into one message
- Use the message tool to send to Discord channel 1197575814494035968
