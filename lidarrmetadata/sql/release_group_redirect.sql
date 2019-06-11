SELECT release_group.gid
  FROM release_group
         JOIN release_group_gid_redirect ON release_group_gid_redirect.new_id = release_group.id
 WHERE release_group_gid_redirect.gid = $1
