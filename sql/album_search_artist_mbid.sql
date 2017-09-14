SELECT
  release.name               AS album,
  release.gid                AS gid,
  area.name                  AS country,
  release_country.date_day   AS day,
  release_country.date_month AS month,
  release_country.date_year  AS year
FROM release
  JOIN release_country ON release.id = release_country.release
  JOIN area ON release_country.country = area.id
  JOIN artist_credit_name ON artist_credit_name.artist_credit = release.artist_credit
  JOIN artist ON artist_credit_name.artist = artist.id
WHERE artist.gid = %s AND area.name = %s