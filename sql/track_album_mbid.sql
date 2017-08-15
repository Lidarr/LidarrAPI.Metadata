SELECT
  track.id,
  track.gid,
  track.name,
  track.position,
  recording.length
FROM track
  JOIN medium ON track.medium = medium.id
  JOIN release ON medium.release = release.id
  JOIN release_group ON release.release_group = release_group.id
  JOIN artist ON release_group.artist_credit = artist.id
  JOIN recording ON track.recording = recording.id
WHERE release_group.gid = %s