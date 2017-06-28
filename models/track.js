module.exports = (sequelize, types) =>
  sequelize.define('track', {
    id: { type: types.UUID, primaryKey: true, defaultValue: types.UUIDV4 },
    mbid: { type: types.STRING, notNull: true },

    title: { type: types.STRING, notNull: true },
    explicit: { type: types.BOOLEAN }
  }, {
    timestamps: true,
    paranoid: true,
    underscored: true
  });
