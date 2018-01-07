SELECT
  release_group.gid                           AS gid,
  release_group.comment,
  release_group_primary_type.name             AS primary_type,
  release_group.name                          AS album,
  release_group_meta.first_release_date_year  AS year,
  release_group_meta.first_release_date_month AS month,
  release_group_meta.first_release_date_day   AS day,
  array(
      SELECT name
      FROM release_group_secondary_type rgst
        JOIN release_group_secondary_type_join rgstj ON rgstj.secondary_type = rgst.id
      WHERE rgstj.release_group = release_group.id
      ORDER BY name ASC
  )                                              secondary_types,
  release.gid                                 AS release_id,
  area.name                                   AS country,
  release.comment                             AS release_comment,
  artist.gid                                  AS artist_id,
  artist.name                                 AS artist_name,
  release_country.date_year                   AS release_year,
  release_country.date_month                  AS release_month,
  release_country.date_day                    AS release_day,
  label.name                                  AS label,
  medium_format.name                          AS format,
  (SELECT COUNT(*)
   FROM medium
   WHERE medium.release = release.id)         AS media_count,
  (SELECT SUM(medium.track_count)
   FROM medium
   WHERE medium.release = release.id)         AS track_count

FROM release_group
  LEFT JOIN release ON release.release_group = release_group.id
  LEFT JOIN release_group_meta ON release_group_meta.id = release_group.id
  LEFT JOIN artist_credit_name ON artist_credit_name.artist_credit = release_group.artist_credit
  LEFT JOIN artist ON artist_credit_name.artist = artist.id
  LEFT JOIN release_group_primary_type ON release_group.type = release_group_primary_type.id
  LEFT JOIN release_label ON release.id = release_label.release
  LEFT JOIN label ON release_label.label = label.id
  LEFT JOIN release_country ON release.id = release_country.release
  LEFT JOIN country_area ON release_country.country = country_area.area
  LEFT JOIN area ON country_area.area = area.id
  LEFT JOIN medium ON medium.release = release.id
  LEFT JOIN medium_format ON medium.format = medium_format.id

WHERE release_group.gid = %s