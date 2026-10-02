-- Reference query for Zulip Server 12.2.
-- Production code uses the equivalent query in ntfy4zulip/database.py.
-- $1 = notification delay in whole minutes (default: 3).
-- $2 = Zulip bot user_id; its realm scopes the query to one organization.
SELECT
    m.id AS message_id,
    m.date_sent,
    m.sender_id,
    sender.full_name AS sender_full_name,
    um.user_profile_id AS target_user_id,
    target.full_name AS target_full_name,
    m.content,
    m.subject AS topic_name,
    m.is_channel_message,
    stream.id AS stream_id,
    stream.name AS stream_name,
    CASE
        WHEN m.is_channel_message THEN NULL
        ELSE ARRAY(
            SELECT dm_sub.user_profile_id
            FROM zerver_subscription AS dm_sub
            WHERE dm_sub.recipient_id = m.recipient_id
            ORDER BY dm_sub.user_profile_id
        )
    END AS dm_user_ids
FROM zerver_message AS m
JOIN zerver_usermessage AS um ON um.message_id = m.id
JOIN zerver_userprofile AS sender ON sender.id = m.sender_id
JOIN zerver_userprofile AS target ON target.id = um.user_profile_id
JOIN zerver_recipient AS recipient ON recipient.id = m.recipient_id
LEFT JOIN zerver_stream AS stream
    ON m.is_channel_message
   AND recipient.type = 2
   AND stream.id = recipient.type_id
WHERE
    m.date_sent >= date_trunc('minute', CURRENT_TIMESTAMP)
                   - ($1 + 1) * INTERVAL '1 minute'
    AND m.date_sent < date_trunc('minute', CURRENT_TIMESTAMP)
                      - $1 * INTERVAL '1 minute'
    AND (um.flags & 1) = 0
    AND um.user_profile_id <> m.sender_id
    AND target.is_active = TRUE
    AND target.is_bot = FALSE
    AND m.realm_id = (
        SELECT realm_id
        FROM zerver_userprofile
        WHERE id = $2
    )
ORDER BY m.id, um.user_profile_id;
