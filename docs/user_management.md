# Users and groups (Table API + role tools)

This fork does **not** register thin MCP wrappers such as `create_user`, `list_users`, or `add_group_members`. User, group, and membership rows are manipulated with the **generic Table API** on the standard tables below. **Role assignment** has dedicated compound tools.

## Tables

| Concept    | Table              |
|-----------|--------------------|
| User      | `sys_user`         |
| Group     | `sys_user_group`   |
| Membership| `sys_user_grmember`|

Use **`query_records`**, **`get_record`**, **`create_record`**, **`update_record`** as appropriate. Always use **`sys_id`** for references (`manager`, `user`, `group`) when the API requires it.

## Compound role tools

When in your package:

- **`grant_role_to_user`** / **`revoke_role_from_user`**  
- **`grant_role_to_group`** / **`revoke_role_from_group`**  

Use these instead of writing `sys_user_has_role` directly unless your runbook specifies otherwise.

## Typical scenarios

### Create a user

`create_record` on `sys_user` with `user_name`, `first_name`, `last_name`, `email`, and optional `department`, `title`, `manager` (reference), etc. Confirm mandatory fields via **`list_table_fields`** or blueprint.

### Find users

`query_records` on `sys_user` with encoded query (department, active, name contains).

### Create a group

`create_record` on `sys_user_group` with `name` and optional `description`, `manager`, `type`.

### Add a user to a group

`create_record` on `sys_user_grmember` with `user` and `group` references (`sys_id`).

### Remove membership

`delete_record` on the specific `sys_user_grmember` row (find it with `query_records` first), or `update_record` if your process deactivates instead of deleting.

### Grant ITIL (or another role)

`grant_role_to_user` with user and role identifiers as defined by the tool params (often `sys_id`).

## Troubleshooting

- **Duplicate user_name:** query first, then update instead of create.  
- **Invalid reference:** resolve manager/group/user with `query_records` before writing.  
- **Role not applied:** confirm role name/sys_id and that the compound tool succeeded.

## See also

- [README](../README.md)  
- [Table introspection](table_introspection.md)  
