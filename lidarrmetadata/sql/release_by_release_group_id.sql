SELECT
  release.gid,
  release.name,
  release.comment,
  release_status.name                                                                 AS status,
  array(
    SELECT name FROM label
    JOIN release_label ON release_label.label = label.id
    WHERE release_label.release = release.id
    ORDER BY name ASC
  )                                                                                   AS label,
  array(
    SELECT name FROM area
    JOIN country_area ON country_area.area = area.id
    JOIN release_country ON release_country.country = country_area.area
    WHERE release_country.release = release.id
  )                                                                                   AS country,
  array(
    SELECT json_build_object(
      'year', date_year,
      'month', date_month,
      'day', date_day) FROM release_country
    WHERE release_country.release = release.id
  )                                                                                   AS release_dates,
  array(
    SELECT json_build_object(
      'Format', medium_format.name,
      'Name', medium.name,
      'Position', medium.position) FROM medium
    JOIN medium_format ON medium_format.id = medium.format
    WHERE medium.release =  release.id
    ORDER BY medium.position
  )                                                                                   AS media,
  (SELECT SUM(medium.track_count) FROM medium WHERE medium.release = release.id)      AS track_count
FROM release
  JOIN release_status ON release_status.id = release.status
  JOIN release_group ON release_group.id = release.release_group
WHERE release_group.gid = %s
