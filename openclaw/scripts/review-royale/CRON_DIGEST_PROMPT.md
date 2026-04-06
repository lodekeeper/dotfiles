# Review Royale Weekly Digest Cron

You are generating the weekly Review Royale digest for the Lodestar team.

## Steps

1. Run `~/.openclaw/workspace/scripts/review-royale/weekly_digest.sh` to get the raw data
2. If output is "NO_DATA", do nothing (reply with just "NO_DATA")
3. Format the data into a Discord message (see template below)
4. Send it to #lodestar-review-royale (channel 1490679163026145290) using the message tool
5. Reply with "DIGEST_SENT" after posting

## Discord Message Template

Format as a Discord message (no markdown tables — use bullet lists). Include:

```
👑 **Review Royale — Weekly Digest** (Week of [date range])

**🏆 Champion of the Week:** [top scorer] ([XP] XP)

**Lodestar Leaderboard**
🥇 [#1] — [XP] XP ([reviews] reviews, [comments] comments)
🥈 [#2] — [XP] XP ([reviews] reviews, [comments] comments)
🥉 [#3] — [XP] XP ([reviews] reviews, [comments] comments)
[remaining entries with ▫️]

**Lodestar-z Leaderboard**
[top 3-5 entries]

**📈 Week in Numbers**
• [total reviews] reviews submitted
• [total XP] XP earned  
• [total comments] comments written
• [reviewer count] active reviewers

[fun closer based on activity level]

🔗 Full leaderboard: <https://review-royale.nflaig.dev/>
```

## Rules
- Use `<url>` format for links (suppresses Discord embeds)
- No markdown tables
- Keep it concise and fun
- If champion has 5000+ XP, roast them for having no life
- If total reviews < 20, shame the team gently
