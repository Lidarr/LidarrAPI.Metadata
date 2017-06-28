module.exports = (sequelize, types) =>
  sequelize.define('image', {
    id: { type: types.UUID, primaryKey: true, defaultValue: types.UUIDV4 },

    url: { type: types.STRING, validate: { isUrl: true } },
    media_type: { type: types.STRING }
  }, {
    timestamps: true,
    paranoid: true,
    underscored: true
  });
