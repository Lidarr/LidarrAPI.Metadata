SELECT DISTINCT
  release_group.gid  AS gid,
  release_group_primary_type.name as primary_type,
  release_group.name AS album,
  array(
    SELECT name FROM release_group_secondary_type rgst
    JOIN release_group_secondary_type_join rgstj ON rgstj.secondary_type = rgst.id
    WHERE rgstj.release_group = release_group.id
    ORDER BY name ASC
  ) secondary_types,
  array(
    SELECT DISTINCT release_status.name FROM release_status
    JOIN release ON release.status = release_status.id
    WHERE release.release_group = release_group.id
  ) release_statuses
FROM release_group
  JOIN artist_credit_name ON artist_credit_name.artist_credit = release_group.artist_credit
  JOIN artist ON artist_credit_name.artist = artist.id
  JOIN release_group_primary_type ON release_group.type = release_group_primary_type.id

WHERE artist.gid = $1 AND artist_credit_name.position = 0
