module.exports = (sequelize, types) =>
  sequelize.define('Artist', {
    id: { type: types.UUID, primaryKey: true, defaultValue: types.UUIDV4 },
    Id: { type: types.STRING, notNull: true }, // mbid

    ArtistName: { type: types.STRING, notNull: true },
    Overview: { type: types.TEXT }
  }, {
    timestamps: true,
    paranoid: true,
    underscored: true
  });
