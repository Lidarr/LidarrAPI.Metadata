SELECT url.url
FROM url
  JOIN release_group ON TRUE   
  JOIN l_release_group_url ON l_release_group_url.entity0 = release_group.id AND l_release_group_url.entity1 = url.id
WHERE release_group.gid = %s
