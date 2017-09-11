SELECT release.name as album,
  release.gid as gid,
  area.name as country,
  release_country.date_day as day,
  release_country.date_month as month,
  release_country.date_year as year
FROM release
  JOIN release_country on release.id = release_country.release
  JOIN area on release_country.country = area.id
  JOIN artist on release.artist_credit = artist.id
  WHERE artist.gid = %s AND area.name = %s