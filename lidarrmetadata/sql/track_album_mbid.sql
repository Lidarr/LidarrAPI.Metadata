SELECT DISTINCT
  track.id,
  track.gid,
  track.name,
  track.position,
  recording.length
FROM track
  JOIN medium ON track.medium = medium.id
  JOIN release ON medium.release = release.id
  JOIN release_group ON release.release_group = release_group.id
  JOIN artist_credit_name ON release.artist_credit = artist_credit_name.artist_credit
  JOIN artist ON artist_credit_name.artist = artist.id
  JOIN recording ON track.recording = recording.id
WHERE release.gid = %s