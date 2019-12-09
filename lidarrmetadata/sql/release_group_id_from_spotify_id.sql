SELECT release_group.gid
FROM release_group
JOIN l_release_group_url ON l_release_group_url.entity0 = release_group.id
JOIN url ON l_release_group_url.entity1 = url.id
WHERE url.url = 'https://open.spotify.com/album/' || $1
