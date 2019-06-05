select
  row_to_json(album_data) album
  from (
    select
      release_group.gid as Id,
      release_group.comment as Disambiguation,
      release_group.name as Title,
      release_group_primary_type.name as Type,
      array(
        SELECT name
          FROM release_group_secondary_type rgst
                 JOIN release_group_secondary_type_join rgstj ON rgstj.secondary_type = rgst.id
         WHERE rgstj.release_group = release_group.id
         ORDER BY name ASC
      ) as SecondaryTypes,
      COALESCE(
        make_date(
          release_group_meta.first_release_date_year,
          release_group_meta.first_release_date_month,
          release_group_meta.first_release_date_day
        ),
        make_date(
          COALESCE(release_group_meta.first_release_date_year, 1),
          COALESCE(release_group_meta.first_release_date_month, 1),
          COALESCE(release_group_meta.first_release_date_day, 1)
        )
      )as ReleaseDate,
      artist.gid as ArtistId,
      array(
	SELECT DISTINCT
	  artist.gid
	  FROM artist
		 JOIN artist_credit_name on artist.id = artist_credit_name.artist
		 JOIN track on track.artist_credit = artist_credit_name.artist_credit
		 JOIN medium on track.medium = medium.id
		 JOIN release on medium.release = release.id
	 WHERE release.release_group = release_group.id
	   AND artist_credit_name.position = 0

         UNION
               
        SELECT
          artist.gid
          FROM artist
                 JOIN artist_credit_name ON artist_credit_name.artist = artist.id
         WHERE artist_credit_name.artist_credit = release_group.artist_credit
           AND artist_credit_name.position = 0
      ) as ArtistIds,	
      json_build_object(
        'Count', COALESCE(release_group_meta.rating_count, 0),
        'Value', release_group_meta.rating / 10
      ) as Rating,
      array(
        SELECT url.url
          FROM url
                 JOIN l_release_group_url ON l_release_group_url.entity0 = release_group.id AND l_release_group_url.entity1 = url.id
      ) as Links,
      (
	SELECT
	  json_agg(row_to_json(images_data))
	  FROM (
	    SELECT unnest(types) AS type,
		   release.gid AS release_gid,
		   index_listing.id AS image_id
	      FROM cover_art_archive.index_listing
		     JOIN release ON index_listing.release = release.id
	     WHERE release.release_group = release_group.id
	  ) images_data
      ) as images,
      (
        SELECT 
          json_agg(row_to_json(releases_data))
          FROM (
            SELECT
              release.gid as Id,
              release.name as Title,
              release.comment as Disambiguation,
              release_status.name as Status,
              (
                SELECT 
                  COALESCE(
                    MIN(make_date(date_year, date_month, date_day)),
                    MIN(make_date(COALESCE(date_year, 1), COALESCE(date_month, 1), COALESCE(date_day, 1)))
                    )
                  FROM (
                    SELECT date_year, date_month, date_day
                      FROM release_country
                     WHERE release_country.release = release.id
                           
                     UNION

                    SELECT date_year, date_month, date_day
                      FROM release_unknown_country
                     WHERE release_unknown_country.release = release.id
                  ) dates
              ) as ReleaseDate,
              array(
                SELECT name FROM label
                                   JOIN release_label ON release_label.label = label.id
                 WHERE release_label.release = release.id
                 ORDER BY name ASC
              ) AS Label,
              array(
                SELECT name FROM area
                                   JOIN country_area ON country_area.area = area.id
                                   JOIN release_country ON release_country.country = country_area.area
                 WHERE release_country.release = release.id
              ) as Country,
              array(
                SELECT json_build_object(
                  'Format', medium_format.name,
                  'Name', medium.name,
                  'Position', medium.position
                ) FROM medium
                         JOIN medium_format ON medium_format.id = medium.format
                 WHERE medium.release =  release.id
                 ORDER BY medium.position
              ) as Media,
              (SELECT SUM(medium.track_count) FROM medium WHERE medium.release = release.id) AS track_count,
              (
                SELECT
                  json_agg(row_to_json(track_data))
                  FROM (
                    SELECT
                      track.gid as Id,
                      recording.gid as RecordingId,
                      artist.gid as ArtistId,
                      track.name as TrackName,
                      track.length as DurationMs,
                      medium.position as MediumNumber,
                      track.number as TrackNumber,
                      track.position as TrackPositon
                      FROM track
                             JOIN medium ON track.medium = medium.id
                             JOIN artist_credit_name ON artist_credit_name.artist_credit = track.artist_credit
                             JOIN artist ON artist_credit_name.artist = artist.id
                             JOIN recording ON track.recording = recording.id
                     WHERE medium.release = release.id
                       AND artist_credit_name.position = 0
                       AND recording.video = FALSE
                       AND track.is_data_track = FALSE
                  ) track_data
              ) as Tracks                                                                                     
              FROM release
                     JOIN release_status ON release_status.id = release.status
             WHERE release.release_group = release_group.id
          ) releases_data
      ) as Releases
      FROM release_group
             LEFT JOIN release_group_meta ON release_group_meta.id = release_group.id
             LEFT JOIN release_group_primary_type ON release_group.type = release_group_primary_type.id
             LEFT JOIN artist_credit_name ON artist_credit_name.artist_credit = release_group.artist_credit
             LEFT JOIN artist ON artist_credit_name.artist = artist.id
     WHERE release_group.gid = ANY($1::uuid[])
  ) album_data;
