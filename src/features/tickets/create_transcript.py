import io
from datetime import datetime

import discord


async def create_transcript(channel: discord.TextChannel) -> io.BytesIO:
    """Create a text transcript of all messages in a channel."""
    transcript = io.StringIO()
    transcript.write(f"Transcript of #{channel.name}\n")
    transcript.write(
        f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    )
    transcript.write("=" * 80 + "\n\n")

    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        messages.append(message)

    for message in messages:
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        transcript.write(
            f"[{timestamp}] {message.author.name} (ID: {message.author.id})\n"
        )
        if message.content:
            transcript.write(f"{message.content}\n")
        if message.attachments:
            transcript.write("Attachments:\n")
            for attachment in message.attachments:
                transcript.write(f"  - {attachment.filename} ({attachment.url})\n")
        if message.embeds:
            transcript.write(f"[{len(message.embeds)} embed(s)]\n")
        transcript.write("\n")

    transcript.write("=" * 80 + "\n")
    transcript.write(f"End of transcript - Total messages: {len(messages)}\n")

    transcript_bytes = io.BytesIO(transcript.getvalue().encode("utf-8"))
    transcript_bytes.seek(0)
    return transcript_bytes
