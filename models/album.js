module.exports = (sequelize, types) =>
  sequelize.define('Album', {
    id: { type: types.UUID, primaryKey: true, defaultValue: types.UUIDV4 },
    Id: { type: types.STRING, notNull: true }, // mbid

    Title: { type: types.STRING, notNull: true },
    ReleaseDate: { type: types.DATEONLY, notNull: true }
  }, {
    timestamps: true,
    paranoid: true,
    underscored: true
  });
