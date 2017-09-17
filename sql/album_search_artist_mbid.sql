SELECT
  release_group.gid  AS gid,
  release_group_primary_type.name as primary_type,
  release_group.name AS album,
  release_group_meta.first_release_date_year AS year,
  release_group_meta.first_release_date_month AS month,
  release_group_meta.first_release_date_day AS day,
    array(
    SELECT name FROM release_group_secondary_type rgst
    JOIN release_group_secondary_type_join rgstj ON rgstj.secondary_type = rgst.id
    WHERE rgstj.release_group = release_group.id
    ORDER BY name ASC
  ) secondary_types,
  array(
    SELECT release.gid FROM release
    LEFT JOIN release_country ON release_country.release = release.id
    LEFT JOIN area ON release_country.country = area.id
    WHERE release.release_group = release_group.id AND release.status = '1'
    ORDER BY date_year, date_month, date_day ASC
  ) releases

FROM release_group
  JOIN release_group_meta ON release_group_meta.id = release_group.id
  JOIN artist_credit_name ON artist_credit_name.artist_credit = release_group.artist_credit
  JOIN artist ON artist_credit_name.artist = artist.id
  JOIN release_group_primary_type ON release_group.type = release_group_primary_type.id

WHERE artist.gid = %s