SELECT
  release_group.gid,
  release_group.comment,
  release_group_primary_type.name                            AS primary_type,
  release_group.name,
  artist.gid                                                 AS artist_id,
  release_group_meta.first_release_date_year                 AS year,
  release_group_meta.first_release_date_month                AS month,
  release_group_meta.first_release_date_day                  AS day,
  release_group_meta.rating,
  release_group_meta.rating_count,
  array(
      SELECT name
      FROM release_group_secondary_type rgst
        JOIN release_group_secondary_type_join rgstj ON rgstj.secondary_type = rgst.id
      WHERE rgstj.release_group = release_group.id
      ORDER BY name ASC
  )                                                             secondary_types

FROM release_group
  LEFT JOIN release_group_meta ON release_group_meta.id = release_group.id
  LEFT JOIN release_group_primary_type ON release_group.type = release_group_primary_type.id
  LEFT JOIN artist_credit_name ON artist_credit_name.artist_credit = release_group.artist_credit
  LEFT JOIN artist ON artist_credit_name.artist = artist.id

WHERE release_group.gid = %s
ORDER BY
  year,
  month,
  day
