Same root mechanism, in a Telegram **direct message**, with no other bot involved:

- The user sent "🎉". The agent (anthropic/claude-opus-5-5 on claude-cli) answered `NO_REPLY`.
- The run ended as a failure instead of a no-op:
  ```
  [agent/cli-backend] cli terminal failure: provider=claude-cli model=claude-opus-5-5 ... error=CLI backend returned an empty response.
  [model-fallback/decision] decision=candidate_failed ... reason=empty_response next=openai/gpt-6.1-sol
  [model-fallback/decision] decision=candidate_succeeded ... candidate=openai/gpt-6.1-sol
  ```
- The fallback model then sent the visible reply, and the user saw a "Model Fallback: openai/gpt-6.1-sol (selected anthropic/claude-opus-5-5; empty response)" notice.

I understand that direct conversations require a visible answer in 9.x. The surprising part is that a deliberate silent token on a required turn gets classified as an `empty_response` **failure**, which triggers a switch to a different provider/model. If an answer is required, re-prompting the primary model (the same visible-answer continuation already used for the fallback model) seems like the better recovery. Cross-provider failover can be kept for real empty or broken outputs. The current behavior can also produce replies in a different voice/model under the bot's name, which is what happened in both the Discord and the DM case.
