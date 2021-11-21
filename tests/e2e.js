/**
 * Post-deploy e2e testing by https://k6.io/. Once k6 is installed, just run
 * k6 run tests/e2e.js
 */
import http from 'k6/http'
import { check, group } from 'k6'

const API_BASE = 'https://api.lidarr.audio/api/testing'

function status200(response) {
    return response.status == 200
}

function fetch(path) {
    path = path === undefined ? '' : path
    return http.get(`${API_BASE}/${path}`)
}

function testRoot() {
    const res = fetch()
    const data = res.json()
    console.log(`Testing against version ${data.version} - ${data.branch}:${data.commit}`)
    check(res, { 'API root returned HTTP 200': status200 })
}

function testBillboardTopAlbums() {
    const res = fetch('chart/billboard/album/top')
    check(res, { 'Charts - Billboard top albums returned HTTP 200': status200 })
}

function testBillboardTopArtists() {
    const res = fetch('chart/billboard/artist/top')
    check(res, { 'Charts - Billboard top artists returned HTTP 200': status200 })
}

function testBillboardCharts() {
    testBillboardTopAlbums()
    testBillboardTopArtists()
}

function testiTunesTopAlbums() {
    const res = fetch('chart/itunes/album/top')
    check(res, { 'Charts - iTunes top albums returned HTTP 200': status200 })
}

function testiTunesNewAlbums() {
    const res = fetch('chart/itunes/album/new')
    check(res, { 'Charts - iTunes new artists returned HTTP 200': status200 })
}

function testiTunesCharts() {
    testiTunesTopAlbums()
    testiTunesNewAlbums()
}

function testAppleMusicTopAlbums() {
    const res = fetch('chart/apple-music/album/top')
    check(res, { 'Charts - Apple Music top albums returned HTTP 200': status200 })
}

function testAppleMusicNewAlbums() {
    const res = fetch('chart/apple-music/album/new')
    check(res, { 'Charts - Apple Music new albums returned HTTP 200': status200 })
}

function testAppleMusicCharts() {
    testAppleMusicTopAlbums()
    testAppleMusicNewAlbums()
}

function testLastFMTopAlbums() {
    const res = fetch('chart/lastfm/album/top')
    check(res, { 'Charts - LastFM top albums returned HTTP 200': status200 })
}

function testLastFMTopArtists() {
    const res = fetch('chart/lastfm/artist/top')
    check(res, { 'Charts - LastFM top artists returned HTTP 200': status200 })
}

function testLastFMCharts() {
    testLastFMTopAlbums()
    testLastFMTopArtists()
}

function testCharts() {
    testBillboardCharts()
    testiTunesCharts()
    testAppleMusicCharts()
    testLastFMCharts()
}

function testArtist() {
    const res = fetch('artist/0743b15a-3c32-48c8-ad58-cb325350befa')
    check(res, { 'Artist - Fetch artist by MBID returned HTTP 200': status200 })
}

function testAlbum() {
    const res = fetch('album/0a467c9c-c9f7-3a86-bce1-c013e3bacd5f')
    check(res, { 'Album - Fetch album by MBID returned HTTP 200': status200 })
}

function testAlbumSearch() {
    const res = fetch('search/album?query=cheshire%20cat')
    check(res, { 'Search - Search artist returned HTTP 200': status200 })
}

function testArtistSearch() {
    const res = fetch('search/artist?query=blink-182')
    check(res, { 'Search - Search album returned HTTP 200': status200 })
}

function testSearch() {
    testAlbumSearch()
    testArtistSearch()
}

export default function () {
    testRoot()
    group('Charts', testCharts)
    group('Artist', testArtist)
    group('Album', testAlbum)
    group('Search', testSearch)
}