// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;
using Kotor.NET.Common.Item;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTC
{
    public class UTCCompiler
    {
        public UTC Read(GFF gff)
        {
            var utc = new UTC();

            utc.ResRef = gff.Root.Get("TemplateResRef", new ResRef())!;
            utc.Conversation = gff.Root.Get("Conversation", new ResRef())!;

            utc.FirstName = gff.Root.Get("FirstName", new LocalizedString())!;
            utc.LastName = gff.Root.Get("LastName", new LocalizedString())!;

            utc.Tag = gff.Root.Get("Tag", "")!;
            utc.Comment = gff.Root.Get("Comment", "")!;

            utc.SubraceID = gff.Root.Get("SubraceIndex", (byte)0);
            utc.PerceptionID = gff.Root.Get("PerceptionRange", (byte)0);
            utc.RaceID = gff.Root.Get("Race", (byte)0);
            utc.AppearanceID = gff.Root.Get("Appearance_Type", (byte)0);
            utc.GenderID = gff.Root.Get("Gender", (byte)0);
            utc.FactionID = gff.Root.Get("FactionID", (byte)0);
            utc.WalkRateID = gff.Root.Get("WalkRate", (byte)0);
            utc.SoundsetID = gff.Root.Get("SoundSetFile", (byte)0);
            utc.PortraitID = gff.Root.Get("PortraitId", (byte)0);
            utc.PaletteID = gff.Root.Get("PaletteID", (byte)0);
            utc.BodyVariation = gff.Root.Get("BodyVariation", (byte)0);
            utc.TextureVariation = gff.Root.Get("TextureVar", (byte)0);

            utc.NotReorientating = gff.Root.Get("NotReorienting", false)!;
            utc.PartyInteract = gff.Root.Get("PartyInteract", false)!;
            utc.NoPermanentDeath = gff.Root.Get("NoPermDeath", false)!;
            utc.Min1HP = gff.Root.Get("Min1HP", false)!;
            utc.Plot = gff.Root.Get("Plot", false)!;
            utc.Interruptable = gff.Root.Get("Interruptable", false)!;
            utc.IsPC = gff.Root.Get("IsPC", false)!;
            utc.Disarmable = gff.Root.Get("Disarmable", false)!;
            utc.IgnoreCreaturePath = gff.Root.Get("IgnoreCrePath", false)!;
            utc.Hologram = gff.Root.Get("Hologram", false)!;

            utc.Alignment = gff.Root.Get("GoodEvil", (byte)0);
            utc.ChallengeRating = gff.Root.Get("ChallengeRating", (byte)0);
            utc.Blindspot = gff.Root.Get("BlindSpot", (byte)0);
            utc.MultiplierSet = gff.Root.Get("MultiplierSet", (byte)0);

            utc.NaturalAC = gff.Root.Get("NaturalAC", (byte)0);
            utc.ReflexBonus = gff.Root.Get("refbonus", (byte)0);
            utc.WillBonus = gff.Root.Get("willbonus", (byte)0);
            utc.FortitudeBonus = gff.Root.Get("fortbonus", (byte)0);

            utc.Strength = gff.Root.Get("Str", (byte)0);
            utc.Dexterity = gff.Root.Get("Dex", (byte)0);
            utc.Constitution = gff.Root.Get("Con", (byte)0);
            utc.Intelligence = gff.Root.Get("Int", (byte)0);
            utc.Wisdom = gff.Root.Get("Wis", (byte)0);
            utc.Charisma = gff.Root.Get("Cha", (byte)0);

            utc.CurrentHP = gff.Root.Get("CurrentHitPoints", (byte)0);
            utc.MaxHP = gff.Root.Get("MaxHitPoints", (byte)0);
            utc.HP = gff.Root.Get("HitPoints", (byte)0);
            utc.MaxFP = gff.Root.Get("ForcePoints", (byte)0);
            utc.FP = gff.Root.Get("CurrentForce", (byte)0);

            utc.OnEndDialog = gff.Root.Get("ScriptEndDialogu", new ResRef())!;
            utc.OnBlocked = gff.Root.Get("ScriptOnBlocked", new ResRef())!;
            utc.OnHeartbeat = gff.Root.Get("ScriptHeartbeat", new ResRef())!;
            utc.OnNotice = gff.Root.Get("ScriptOnNotice", new ResRef())!;
            utc.OnSpell = gff.Root.Get("ScriptSpellAt", new ResRef())!;
            utc.OnAttack = gff.Root.Get("ScriptAttacked", new ResRef())!;
            utc.OnDamaged = gff.Root.Get("ScriptDamaged", new ResRef())!;
            utc.OnDisturbed = gff.Root.Get("ScriptDisturbed", new ResRef())!;
            utc.OnEndRound = gff.Root.Get("ScriptEndRound", new ResRef())!;
            utc.OnDialog = gff.Root.Get("ScriptDialogue", new ResRef())!;
            utc.OnSpawn = gff.Root.Get("ScriptSpawn", new ResRef())!;
            utc.OnRested = gff.Root.Get("ScriptRested", new ResRef())!;
            utc.OnDeath = gff.Root.Get("ScriptDeath", new ResRef())!;
            utc.OnUserDefined = gff.Root.Get("ScriptUserDefine", new ResRef())!;

            var skillList = gff.Root.Get("SkillList", new GFFList())!;
            utc.ComputerUse = skillList.Get(0).Get("Rank", (byte)0);
            utc.Demolitions = skillList.Get(1).Get("Rank", (byte)0);
            utc.Stealth = skillList.Get(2).Get("Rank", (byte)0);
            utc.Awareness = skillList.Get(3).Get("Rank", (byte)0);
            utc.Persuade = skillList.Get(4).Get("Rank", (byte)0);
            utc.Repair = skillList.Get(5).Get("Rank", (byte)0);
            utc.Security = skillList.Get(6).Get("Rank", (byte)0);
            utc.TreatInjury = skillList.Get(7).Get("Rank", (byte)0);

            var classList = gff.Root.Get("ClassList", new GFFList());
            foreach (var classStruct in classList)
            {
                var @class = new Class();
                @class.ClassID = classStruct.Get("Class", 0);
                @class.ClassLevel = classStruct.Get("ClassLevel", 0);
                utc.Classes.Add(@class);

                var powerList = classStruct.Get("KnownList0", new GFFList())!;
                foreach (var powerStruct in powerList)
                {
                    var power = new ForcePower();
                    power.ForcePowerID = powerStruct.Get("Spell", 0);
                    @class.ForcePowers.Add(power);
                }
            }

            var featList = gff.Root.Get("FeatList", new GFFList());
            foreach (var featStruct in featList)
            {
                utc.Feats.Add(new Feat
                {
                    FeatID = featStruct.Get("Feat", 0),
                });
            }

            var equipmentList = gff.Root.Get("Equip_ItemList", new GFFList());
            foreach (var itemStruct in equipmentList)
            {
                utc.Equipment.Add(new EquippedItem
                {
                    ResRef = itemStruct.Get("EquippedRes", new ResRef()),
                    Droppable = itemStruct.Get("Dropable", false),
                    Slot = (EquipmentSlot)Math.Sqrt(itemStruct.ID)
                });
            }

            var itemList = gff.Root.Get("ItemList", new GFFList());
            foreach (var itemStruct in itemList)
            {
                utc.Inventory.Add(new StoredItem
                {
                    ResRef = itemStruct.Get("EquippedRes", new ResRef()),
                    Droppable = itemStruct.Get("Dropable", false),
                });
            }


            utc.BodyBagID = gff.Root.Get("BodyBag", (byte)0);
            utc.Deity = gff.Root.Get("Deity", "");
            utc.Description = gff.Root.Get("Description", new LocalizedString());
            utc.Lawfulness = gff.Root.Get("LawfulChaotic", (byte)0);
            utc.PhenotypeID = gff.Root.Get("Phenotype", 0);
            utc.SubraceName = gff.Root.Get("Subrace", "");

            return utc;
        }
    }
}
