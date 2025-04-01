    @app_commands.command(name="editleveling", description="Configure the leveling system (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def edit_leveling(self, interaction: discord.Interaction):
        """Open a panel to edit leveling system settings."""

        settings = self.db.get_settings()

        embed = discord.Embed(
            title="Leveling System Settings",
            description="Use the buttons below to adjust the leveling system settings.",
            color=discord.Color.green()
        )

        xp_status = settings.get('xp_enabled', 1)
        status_text = "✅ **Enabled**" if xp_status else "❌ **Disabled**"
        status_note = "" if xp_status else "\n*Use /xpstart to enable XP gain*"
        
        embed.add_field(
            name="XP Status",
            value=f"{status_text}{status_note}",
            inline=False
        )

        min_xp = settings.get('min_xp_per_message', 0)
        max_xp = settings.get('max_xp_per_message', 0)
        
        if min_xp > 0 and max_xp > 0 and min_xp != max_xp:

            embed.add_field(
                name="XP Per Message",
                value=f"🎲 **{min_xp}-{max_xp}** (random)",
                inline=True
            )
        else:

            embed.add_field(
                name="XP Per Message",
                value=f"🔢 **{settings['xp_per_message']}**",
                inline=True
            )
        
        embed.add_field(
            name="Coins Per Level Up",
            value=f"💰 **{settings['coins_per_level']}**",
            inline=True
        )
        
        embed.add_field(
            name="XP Cooldown",
            value=f"⏱️ **{settings['xp_cooldown']}** seconds",
            inline=True
        )
        
        embed.add_field(
            name="Base XP Required",
            value=f"📊 **{settings['base_xp_required']}** XP\n*(Level 1: {settings['base_xp_required']}, Level 2: {settings['base_xp_required']*2}, etc.)*",
            inline=False
        )

        view = LevelingSettingsView(self.db, self.bot)
        
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"Edit leveling settings panel opened by {interaction.user}")