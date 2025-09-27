import discord
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

async def get_member_safely(guild: discord.Guild, user_id: int) -> Optional[discord.Member]:
	"""Safely fetch a member by ID, returning None if not found.
	
	Args:
		guild: The Discord guild to search in
		user_id: The ID of the user to fetch
		
	Returns:
		Optional[discord.Member]: The member if found, None otherwise
	"""
	try:
		return await guild.fetch_member(user_id)
	except discord.NotFound:
		logger.warning(f"Member {user_id} not found in guild {guild.name}")
		return None
	except discord.HTTPException as e:
		logger.error(f"Failed to fetch member {user_id}: {e}")
		return None

async def get_role_safely(guild: discord.Guild, role_id: int) -> Optional[discord.Role]:
	"""Safely fetch a role by ID, returning None if not found.
	
	Args:
		guild: The Discord guild to search in
		role_id: The ID of the role to fetch
		
	Returns:
		Optional[discord.Role]: The role if found, None otherwise
	"""
	try:
		role = guild.get_role(role_id)
		if role is None:
			logger.warning(f"Role {role_id} not found in guild {guild.name}")
		return role
	except Exception as e:
		logger.error(f"Failed to fetch role {role_id}: {e}")
		return None

def create_permission_overwrites(
	everyone_permissions: Dict[str, bool],
	allowed_roles: List[int],
	guild: discord.Guild,
	owner: discord.Member
) -> Dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
	"""Create permission overwrites for a temp voice channel.
	
	Args:
		everyone_permissions: Dictionary with view_channel and connect permissions for @everyone
		allowed_roles: List of role IDs that should have access
		guild: The Discord guild
		owner: The channel owner (gets full permissions)
		
	Returns:
		Dict[discord.abc.Snowflake, discord.PermissionOverwrite]: Permission overwrites
	"""
	overwrites = {}
	
	# Set @everyone permissions
	everyone_overwrite = discord.PermissionOverwrite(
		view_channel=everyone_permissions.get("view_channel", True),
		connect=everyone_permissions.get("connect", True)
	)
	overwrites[guild.default_role] = everyone_overwrite
	
	# Grant permissions to allowed roles
	for role_id in allowed_roles:
		role = guild.get_role(role_id)
		if role:
			role_overwrite = discord.PermissionOverwrite(
				view_channel=True,
				connect=True
			)
			overwrites[role] = role_overwrite
			logger.debug(f"Added permissions for role {role.name} ({role_id})")
		else:
			logger.warning(f"Role {role_id} not found in guild {guild.name}")
	
	# Give full permissions to channel owner
	owner_overwrite = discord.PermissionOverwrite(
		view_channel=True,
		connect=True,
		manage_channels=True,
		manage_permissions=True,
		move_members=True,
		mute_members=True,
		deafen_members=True
	)
	overwrites[owner] = owner_overwrite
	
	return overwrites

def apply_privacy_overwrites(
	base_overwrites: Dict[discord.abc.Snowflake, discord.PermissionOverwrite],
	privacy_action: str,
	guild: discord.Guild,
	allowed_roles: List[int],
	owner: discord.Member,
	trusted_users: List[int] = None
) -> Dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
	"""Apply privacy settings. Lock and invisible actions override allowed roles.
	
	Args:
		base_overwrites: Base permission overwrites
		privacy_action: Privacy action (lock, unlock, invisible, visible, etc.)
		guild: The Discord guild
		allowed_roles: List of role IDs that should maintain access (except during lock/invisible)
		owner: The channel owner
		trusted_users: List of trusted user IDs (optional)
		
	Returns:
		Dict[discord.abc.Snowflake, discord.PermissionOverwrite]: Updated overwrites
	"""
	# DEBUG: Log function entry
	print(f"[TEMPVOICE DEBUG] 🔧 APPLY_PRIVACY_OVERWRITES START")
	print(f"[TEMPVOICE DEBUG] 🔧 Action: {privacy_action}")
	print(f"[TEMPVOICE DEBUG] 🔧 Guild: {guild.name} ({guild.id})")
	print(f"[TEMPVOICE DEBUG] 🔧 Owner: {owner.name} ({owner.id})")
	print(f"[TEMPVOICE DEBUG] 🔧 Allowed Roles: {allowed_roles}")
	print(f"[TEMPVOICE DEBUG] 🔧 Trusted Users: {trusted_users}")
	print(f"[TEMPVOICE DEBUG] 🔧 Base Overwrites Count: {len(base_overwrites)}")
	
	overwrites = base_overwrites.copy()
	trusted_users = trusted_users or []
	
	# Special reconcile mode: only clean member overwrites + re-apply trusted/owner; do NOT change role/@everyone overwrites
	if privacy_action == "reconcile":
		print(f"[TEMPVOICE DEBUG] 🤝 RECONCILE MODE: Preserving current role/@everyone overwrites")
		default_ovr = overwrites.get(guild.default_role, discord.PermissionOverwrite())
		# Determine effective state from current @everyone overwrites
		if default_ovr.connect is False:
			effective_state = "lock" if (default_ovr.view_channel is True) else "invisible"
		elif default_ovr.view_channel is False:
			effective_state = "invisible"
		else:
			effective_state = "unlock"
		print(f"[TEMPVOICE DEBUG] 🤝 RECONCILE: Effective state based on @everyone: {effective_state}")
		
		print(f"[TEMPVOICE DEBUG] 🧹 CLEANUP: Scanning member overwrites for removal (reconcile)")
		to_delete = []
		for target, perms in overwrites.items():
			is_member = hasattr(target, "roles") and hasattr(target, "id")
			if not is_member:
				continue
			if target.id == owner.id or target.id in trusted_users:
				continue
			if effective_state in ("lock", "invisible"):
				# Strict cleanup: remove all non-owner/non-trusted member overwrites
				to_delete.append(target)
			else:
				# Non-strict: remove overwrites that only grant without explicit denies
				grants_view = (getattr(perms, "view_channel", None) is True)
				grants_connect = (getattr(perms, "connect", None) is True)
				explicit_deny = (getattr(perms, "view_channel", None) is False) or (getattr(perms, "connect", None) is False) or (getattr(perms, "send_messages", None) is False)
				if (grants_view or grants_connect) and not explicit_deny:
					to_delete.append(target)
		for member in to_delete:
			name = getattr(member, "name", str(member))
			print(f"[TEMPVOICE DEBUG] 🧹 CLEANUP: Removing member overwrite for {name} ({member.id}) in reconcile mode")
			del overwrites[member]
		
		# Handle trusted users
		print(f"[TEMPVOICE DEBUG] 👥 Processing {len(trusted_users)} trusted users (reconcile)")
		for user_id in trusted_users:
			member = guild.get_member(user_id)
			if member:
				overwrites[member] = discord.PermissionOverwrite(
					view_channel=True,
					connect=True
				)
				print(f"[TEMPVOICE DEBUG] 👥 Added trusted user: {member.name} ({member.id}) - view_channel=True, connect=True")
			else:
				print(f"[TEMPVOICE DEBUG] 👥 Trusted user {user_id} not found in guild")
		
		# Ensure owner always has full permissions
		print(f"[TEMPVOICE DEBUG] 👑 Setting owner permissions for {owner.name} ({owner.id}) (reconcile)")
		overwrites[owner] = discord.PermissionOverwrite(
			view_channel=True,
			connect=True,
			manage_channels=True,
			manage_permissions=True,
			move_members=True,
			mute_members=True,
			deafen_members=True
		)
		print(f"[TEMPVOICE DEBUG] 👑 Owner permissions set - full access granted (reconcile)")
		
		print(f"[TEMPVOICE DEBUG] 🔧 FINAL OVERWRITES SUMMARY ({len(overwrites)} total) [reconcile]:")
		for target, perms in overwrites.items():
			if target == guild.default_role:
				print(f"[TEMPVOICE DEBUG] 🔧 @everyone: view_channel={perms.view_channel}, connect={perms.connect}, send_messages={perms.send_messages}")
			elif target == owner:
				print(f"[TEMPVOICE DEBUG] 🔧 Owner {owner.name}: view_channel={perms.view_channel}, connect={perms.connect}, manage_channels={perms.manage_channels}")
			elif hasattr(target, 'name') and hasattr(target, 'id'):
				if hasattr(target, 'roles'):
					print(f"[TEMPVOICE DEBUG] 🔧 Member {target.name} ({target.id}): view_channel={perms.view_channel}, connect={perms.connect}")
				else:
					print(f"[TEMPVOICE DEBUG] 🔧 Role {target.name} ({target.id}): view_channel={perms.view_channel}, connect={perms.connect}")
		print(f"[TEMPVOICE DEBUG] 🔧 APPLY_PRIVACY_OVERWRITES END (reconcile)")
		return overwrites
	
	# 🧹 CLEANUP: Remove member-specific overwrites for users no longer trusted
	print(f"[TEMPVOICE DEBUG] 🧹 CLEANUP: Scanning member overwrites for removal")
	# For strict privacy states (lock/invisible), remove ALL non-owner/non-trusted member overwrites
	if privacy_action in ("lock", "invisible"):
		to_delete = []
		for target, perms in overwrites.items():
			# Identify member targets
			is_member = hasattr(target, "roles") and hasattr(target, "id")
			if not is_member:
				continue
			# Skip owner and currently trusted users
			if target.id == owner.id or target.id in trusted_users:
				continue
			to_delete.append(target)
		for member in to_delete:
			name = getattr(member, "name", str(member))
			print(f"[TEMPVOICE DEBUG] 🧹 CLEANUP: Removing member overwrite for {name} ({member.id}) due to privacy='{privacy_action}'")
			del overwrites[member]
	else:
		# For other states, remove overwrites that explicitly grant access without denies
		to_delete = []
		for target, perms in overwrites.items():
			is_member = hasattr(target, "roles") and hasattr(target, "id")
			if not is_member:
				continue
			if target.id == owner.id or target.id in trusted_users:
				continue
			grants_view = (getattr(perms, "view_channel", None) is True)
			grants_connect = (getattr(perms, "connect", None) is True)
			explicit_deny = (getattr(perms, "view_channel", None) is False) or (getattr(perms, "connect", None) is False) or (getattr(perms, "send_messages", None) is False)
			if (grants_view or grants_connect) and not explicit_deny:
				to_delete.append(target)
		for member in to_delete:
			name = getattr(member, "name", str(member))
			print(f"[TEMPVOICE DEBUG] 🧹 CLEANUP: Removing stale overwrite for member {name} ({member.id})")
			del overwrites[member]
	
	if privacy_action == "lock":
		# Deny connect for @everyone and allowed roles - only owner and trusted users can connect
		print(f"[TEMPVOICE DEBUG] 🔒 LOCK ACTION: Denying connect for @everyone and allowed roles")
		overwrites[guild.default_role] = discord.PermissionOverwrite(
			view_channel=overwrites[guild.default_role].view_channel,
			connect=False
		)
		print(f"[TEMPVOICE DEBUG] 🔒 LOCK: @everyone now has view_channel={overwrites[guild.default_role].view_channel}, connect=False")
		
		# For lock action: allowed roles can see but cannot connect
		for role_id in allowed_roles:
			role = guild.get_role(role_id)
			if role:
				overwrites[role] = discord.PermissionOverwrite(
					view_channel=True,
					connect=False
				)
				print(f"[TEMPVOICE DEBUG] 🔒 LOCK: Role {role.name} ({role_id}) can see but cannot connect - view_channel=True, connect=False")
		
	elif privacy_action == "unlock":
		# Allow connect for @everyone (restore base permission)
		print(f"[TEMPVOICE DEBUG] 🔓 UNLOCK ACTION: Allowing connect for @everyone")
		overwrites[guild.default_role] = discord.PermissionOverwrite(
			view_channel=overwrites[guild.default_role].view_channel,
			connect=True
		)
		print(f"[TEMPVOICE DEBUG] 🔓 UNLOCK: @everyone now has view_channel={overwrites[guild.default_role].view_channel}, connect=True")
		
		# Restore allowed roles permissions during unlock
		for role_id in allowed_roles:
			role = guild.get_role(role_id)
			if role:
				overwrites[role] = discord.PermissionOverwrite(
					view_channel=True,
					connect=True
				)
				print(f"[TEMPVOICE DEBUG] 🔓 UNLOCK: Role {role.name} ({role_id}) access restored - view_channel=True, connect=True")
		
	elif privacy_action == "invisible":
		# Deny view_channel for @everyone and allowed roles - only owner and trusted users can see
		print(f"[TEMPVOICE DEBUG] 👻 INVISIBLE ACTION: Denying view_channel and connect for @everyone and allowed roles")
		overwrites[guild.default_role] = discord.PermissionOverwrite(
			view_channel=False,
			connect=False
		)
		print(f"[TEMPVOICE DEBUG] 👻 INVISIBLE: @everyone now has view_channel=False, connect=False")
		
		# Override allowed roles permissions during invisible
		for role_id in allowed_roles:
			role = guild.get_role(role_id)
			if role:
				overwrites[role] = discord.PermissionOverwrite(
					view_channel=False,
					connect=False
				)
				print(f"[TEMPVOICE DEBUG] 👻 INVISIBLE: Role {role.name} ({role_id}) denied access - view_channel=False, connect=False")
		
	elif privacy_action == "visible":
		# Allow view_channel for @everyone (restore base permission)
		print(f"[TEMPVOICE DEBUG] 👁️ VISIBLE ACTION: Allowing view_channel for @everyone")
		overwrites[guild.default_role] = discord.PermissionOverwrite(
			view_channel=True,
			connect=overwrites[guild.default_role].connect
		)
		print(f"[TEMPVOICE DEBUG] 👁️ VISIBLE: @everyone now has view_channel=True, connect={overwrites[guild.default_role].connect}")
		
		# Restore allowed roles permissions during visible
		for role_id in allowed_roles:
			role = guild.get_role(role_id)
			if role:
				overwrites[role] = discord.PermissionOverwrite(
					view_channel=True,
					connect=True
				)
				print(f"[TEMPVOICE DEBUG] 👁️ VISIBLE: Role {role.name} ({role_id}) access restored - view_channel=True, connect=True")
		
	elif privacy_action == "close_chat":
		# Deny send_messages for @everyone
		print(f"[TEMPVOICE DEBUG] 🤐 CLOSE_CHAT ACTION: Denying send_messages for @everyone")
		current_overwrite = overwrites.get(guild.default_role, discord.PermissionOverwrite())
		overwrites[guild.default_role] = discord.PermissionOverwrite(
			view_channel=current_overwrite.view_channel,
			connect=current_overwrite.connect,
			send_messages=False
		)
		print(f"[TEMPVOICE DEBUG] 🤐 CLOSE_CHAT: @everyone now has send_messages=False")
		
	elif privacy_action == "open_chat":
		# Allow send_messages for @everyone
		print(f"[TEMPVOICE DEBUG] 💬 OPEN_CHAT ACTION: Allowing send_messages for @everyone")
		current_overwrite = overwrites.get(guild.default_role, discord.PermissionOverwrite())
		overwrites[guild.default_role] = discord.PermissionOverwrite(
			view_channel=current_overwrite.view_channel,
			connect=current_overwrite.connect,
			send_messages=True
		)
		print(f"[TEMPVOICE DEBUG] 💬 OPEN_CHAT: @everyone now has send_messages=True")
	
	# Process trusted users and owner - they always maintain access
	print(f"[TEMPVOICE DEBUG] 🔧 PROCESSING TRUSTED USERS AND OWNER")
	
	# Handle trusted users
	print(f"[TEMPVOICE DEBUG] 👥 Processing {len(trusted_users)} trusted users")
	for user_id in trusted_users:
		member = guild.get_member(user_id)
		if member:
			overwrites[member] = discord.PermissionOverwrite(
				view_channel=True,
				connect=True
			)
			print(f"[TEMPVOICE DEBUG] 👥 Added trusted user: {member.name} ({member.id}) - view_channel=True, connect=True")
		else:
			print(f"[TEMPVOICE DEBUG] 👥 Trusted user {user_id} not found in guild")
	
	# Ensure owner always has full permissions
	print(f"[TEMPVOICE DEBUG] 👑 Setting owner permissions for {owner.name} ({owner.id})")
	overwrites[owner] = discord.PermissionOverwrite(
		view_channel=True,
		connect=True,
		manage_channels=True,
		manage_permissions=True,
		move_members=True,
		mute_members=True,
		deafen_members=True
	)
	print(f"[TEMPVOICE DEBUG] 👑 Owner permissions set - full access granted")
	
	# DEBUG: Log final overwrites summary
	print(f"[TEMPVOICE DEBUG] 🔧 FINAL OVERWRITES SUMMARY ({len(overwrites)} total):")
	for target, perms in overwrites.items():
		if target == guild.default_role:
			print(f"[TEMPVOICE DEBUG] 🔧 @everyone: view_channel={perms.view_channel}, connect={perms.connect}, send_messages={perms.send_messages}")
		elif target == owner:
			print(f"[TEMPVOICE DEBUG] 🔧 Owner {owner.name}: view_channel={perms.view_channel}, connect={perms.connect}, manage_channels={perms.manage_channels}")
		elif hasattr(target, 'name') and hasattr(target, 'id'):
			if hasattr(target, 'roles'):
				print(f"[TEMPVOICE DEBUG] 🔧 Member {target.name} ({target.id}): view_channel={perms.view_channel}, connect={perms.connect}")
			else:
				print(f"[TEMPVOICE DEBUG] 🔧 Role {target.name} ({target.id}): view_channel={perms.view_channel}, connect={perms.connect}")
	
	print(f"[TEMPVOICE DEBUG] 🔧 APPLY_PRIVACY_OVERWRITES END")
	return overwrites