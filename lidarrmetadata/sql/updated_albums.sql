SELECT release_group.gid
  FROM release_group
 WHERE release_group.last_updated > $1

 UNION

SELECT gid
  FROM release_group_gid_redirect
 WHERE created > $1

 UNION

SELECT DISTINCT release_group.gid
  FROM release_group
         JOIN release on release.release_group = release_group.id
 WHERE release.last_updated > $1

 UNION

SELECT DISTINCT release_group.gid
  FROM release_group
         JOIN release on release.release_group = release_group.id
         JOIN medium on medium.release = release.id
 WHERE medium.last_updated > $1

 UNION

SELECT DISTINCT release_group.gid
  FROM release_group
         JOIN release ON release.release_group = release_group.id
         JOIN medium ON medium.release = release.id
         JOIN track ON track.medium = medium.id
 WHERE track.last_updated > $1

 UNION

SELECT DISTINCT release_group.gid
  FROM release_group
         JOIN release ON release.release_group = release_group.id
         JOIN medium ON medium.release = release.id
         JOIN track ON track.medium = medium.id
         JOIN recording ON track.recording = recording.id
 WHERE recording.last_updated > $1

 UNION

SELECT DISTINCT release_group.gid
  FROM release_group
         JOIN l_release_group_url ON l_release_group_url.entity0 = release_group.id
         JOIN url ON l_release_group_url.entity1 = url.id
  WHERE url.last_updated > $1
