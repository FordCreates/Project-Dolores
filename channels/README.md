# Channels

> ⚠️ **Status: design reference, not yet implemented.**

The reference character uses Telegram via OpenClaw's built-in channel support, with acknowledged delivery and session persistence handled by `scripts/send_and_append.py`. This directory contains only this README. See [ARCHITECTURE.md §8](../docs/ARCHITECTURE.md#8-messaging-channel-interface) for the proposed interface and current migration requirements.

To use a different channel, align OpenClaw channel/account and DM scope, the Send script's transport/account/target and acknowledgement parsing, session path/key settings in both `scripts/lib/session_append.py` and `scripts/inject_context.py`, Heartbeat's session lookup, and command cron failure-alert destinations. Preserve acknowledgement-before-append, idempotent session append and compare-and-clear of pending content. Changing only OpenClaw configuration and a log path is insufficient.
