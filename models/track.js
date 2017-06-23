module.exports = (sequelize, types) =>
  sequelize.define('track', {
    id: { type: types.UUID, primaryKey: true, defaultValue: types.UUIDV4 },

    title: { type: types.STRING, required: true },
    number: { type: types.INTEGER, required: true }
  }, {
    timestamps: true,
    paranoid: true,
    underscored: true
  });
