// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTC
{
    public class UTCWriter
    {
        public GFF Write(UTC utc)
        {
            var gff = new GFF();

            gff.Root.Set("TemplateResRef", utc.ResRef);
            gff.Root.Set("Conversation", utc.Conversation);

            gff.Root.Set("FirstName", utc.FirstName);
            gff.Root.Set("LastName", utc.LastName);

            gff.Root.Set("Tag", utc.Tag);
            gff.Root.Set("Comment", utc.Comment);

            gff.Root.Set("SubraceIndex", utc.SubraceID);
            gff.Root.Set("PerceptionRange", utc.PerceptionID);
            gff.Root.Set("Race", utc.RaceID);
            gff.Root.Set("Appearance_Type", utc.AppearanceID);
            gff.Root.Set("Gender", utc.GenderID);
            gff.Root.Set("FactionID", utc.FactionID);
            gff.Root.Set("WalkRate", utc.WalkRateID);
            gff.Root.Set("SoundSetFile", utc.SoundsetID);
            gff.Root.Set("PortraitId", utc.PortraitID);
            gff.Root.Set("PaletteID", utc.PaletteID);
            gff.Root.Set("BodyVariation", utc.BodyVariation);
            gff.Root.Set("TextureVar", utc.TextureVariation);

            gff.Root.Set("NotReorienting", Convert.ToByte(utc.NotReorientating));
            gff.Root.Set("PartyInteract", Convert.ToByte(utc.PartyInteract));
            gff.Root.Set("NoPermDeath", Convert.ToByte(utc.NoPermanentDeath));
            gff.Root.Set("Min1HP", Convert.ToByte(utc.Min1HP));
            gff.Root.Set("Plot", Convert.ToByte(utc.Plot));
            gff.Root.Set("Interruptable", Convert.ToByte(utc.Interruptable));
            gff.Root.Set("IsPC", Convert.ToByte(utc.IsPC));
            gff.Root.Set("Disarmable", Convert.ToByte(utc.Disarmable));
            gff.Root.Set("IgnoreCrePath", Convert.ToByte(utc.IgnoreCreaturePath));
            gff.Root.Set("Hologram", Convert.ToByte(utc.Hologram));

            return gff;
        }
    }
}
