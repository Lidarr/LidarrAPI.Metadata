SELECT DISTINCT
  release_group.gid  AS gid,
  release_group.comment,
  release_group_primary_type.name as primary_type,
  release_group.name AS album,
  release_group_meta.first_release_date_year AS year,
  release_group_meta.first_release_date_month AS month,
  release_group_meta.first_release_date_day AS day,
  release_group_meta.rating,
  release_group_meta.rating_count,
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
  JOIN release_group_meta ON release_group_meta.id = release_group.id
  JOIN artist_credit_name ON artist_credit_name.artist_credit = release_group.artist_credit
  JOIN artist ON artist_credit_name.artist = artist.id
  JOIN release_group_primary_type ON release_group.type = release_group_primary_type.id

WHERE artist.gid = %s AND artist_credit_name.position = 0
