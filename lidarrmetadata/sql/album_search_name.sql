SELECT
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
    SELECT release.gid FROM release
    LEFT JOIN release_country ON release_country.release = release.id
    LEFT JOIN area ON release_country.country = area.id
    WHERE release.release_group = release_group.id
    ORDER BY date_year, date_month, date_day ASC, status DESC
  ) releases,
  artist.name AS artist_name,
  artist.gid AS artist_id

FROM release_group
  JOIN release_group_meta ON release_group_meta.id = release_group.id
  JOIN artist_credit_name ON artist_credit_name.artist_credit = release_group.artist_credit
  JOIN artist ON artist_credit_name.artist = artist.id
  JOIN release_group_primary_type ON release_group.type = release_group_primary_type.id

WHERE UPPER(release_group.name) LIKE UPPER(%s)
ORDER BY
  CASE WHEN UPPER(release_group.name) = UPPER(%s) THEN 0 ELSE 1 END,
  CASE WHEN (release_group_meta.rating_count * release_group_meta.rating) IS NULL THEN 0 ELSE (release_group_meta.rating_count * release_group_meta.rating) END DESC