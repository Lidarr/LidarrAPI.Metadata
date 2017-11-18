SELECT
  release_group.gid                           AS gid,
  release_group.comment,
  release_group_primary_type.name             AS primary_type,
  release_group.name                          AS album,
  release_group_meta.first_release_date_year  AS year,
  release_group_meta.first_release_date_month AS month,
  release_group_meta.first_release_date_day   AS day,
  array_agg(release_group_alias.name)         AS aliases,
  array(
      SELECT name
      FROM release_group_secondary_type rgst
        JOIN release_group_secondary_type_join rgstj ON rgstj.secondary_type = rgst.id
      WHERE rgstj.release_group = release_group.id
      ORDER BY name ASC
  )                                              secondary_types,
  array(
      SELECT release.gid
      FROM release
        LEFT JOIN release_country ON release_country.release = release.id
        LEFT JOIN area ON release_country.country = area.id
      WHERE release.release_group = release_group.id
      ORDER BY date_year, date_month, date_day ASC, status DESC
  )                                              releases

FROM release_group
  JOIN release_group_meta ON release_group_meta.id = release_group.id
  JOIN artist_credit_name ON artist_credit_name.artist_credit = release_group.artist_credit
  JOIN artist ON artist_credit_name.artist = artist.id
  JOIN release_group_primary_type ON release_group.type = release_group_primary_type.id
  FULL JOIN release_group_alias ON release_group_alias.release_group = release_group.id

WHERE artist.gid = %s AND artist_credit_name.position = 0
GROUP BY release_group.gid, release_group.comment,
  release_group_primary_type.name,
  release_group.name,
  release_group_meta.first_release_date_year,
  release_group_meta.first_release_date_month,
  release_group_meta.first_release_date_day,
  secondary_types,
  releases