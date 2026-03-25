using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTD
{
    public class UTDCompiler : IGFFDecompiler<UTD>
    {
        private GFF _gff;

        public UTDCompiler(GFF gff)
        {
            _gff = gff;
        }

        public UTD Decompile()
        {
            var utd = new UTD
            {
                AnimationState = _gff.Root.GetUInt8("AnimationState", 0),
                Appearance = _gff.Root.GetUInt32("Appearance", 0),
                AutoRemoveKey = _gff.Root.GetUInt8("AutoRemoveKey", 0),
                CloseLockDC = _gff.Root.GetUInt8("CloseLockDC", 0),
                Comment = _gff.Root.GetString("Comment", ""),
                Conversation = _gff.Root.GetResRef("Conversation", new ResRef()),
                CurrentHP = _gff.Root.GetInt16("CurrentHP", 0),
                Description = _gff.Root.GetLocalizedString("Description", new LocalizedString()),
                DisarmDC = _gff.Root.GetUInt8("DisarmDC", 0),
                Faction = _gff.Root.GetUInt32("Faction", 0),
                Fort = _gff.Root.GetUInt8("Fort", 0),
                GenericType = _gff.Root.GetUInt8("GenericType", 0),
                Hardness = _gff.Root.GetUInt8("Hardness", 0),
                HP = _gff.Root.GetInt16("HP", 0),
                Interruptable = _gff.Root.GetUInt8("Interruptable", 0),
                KeyName = _gff.Root.GetString("KeyName", ""),
                KeyRequired = _gff.Root.GetUInt8("KeyRequired", 0),
                LoadScreenID = _gff.Root.GetUInt16("LoadScreenID", 0),
                Lockable = _gff.Root.GetUInt8("Lockable", 0),
                Locked = _gff.Root.GetUInt8("Locked", 0),
                LocName = _gff.Root.GetLocalizedString("LocName", new LocalizedString()),
                Min1HP = _gff.Root.GetUInt8("Min1HP", 0),
                NotBlastable = _gff.Root.GetUInt8("NotBlastable", 0),
                OnClick = _gff.Root.GetResRef("OnClick", new ResRef()),
                OnClosed = _gff.Root.GetResRef("OnClosed", new ResRef()),
                OnDamaged = _gff.Root.GetResRef("OnDamaged", new ResRef()),
                OnDeath = _gff.Root.GetResRef("OnDeath", new ResRef()),
                OnDisarm = _gff.Root.GetResRef("OnDisarm", new ResRef()),
                OnFailToOpen = _gff.Root.GetResRef("OnFailToOpen", new ResRef()),
                OnHeartbeat = _gff.Root.GetResRef("OnHeartbeat", new ResRef()),
                OnLock = _gff.Root.GetResRef("OnLock", new ResRef()),
                OnMeleeAttacked = _gff.Root.GetResRef("OnMeleeAttacked", new ResRef()),
                OnOpen = _gff.Root.GetResRef("OnOpen", new ResRef()),
                OnSpellCastAt = _gff.Root.GetResRef("OnSpellCastAt", new ResRef()),
                OnTrapTriggered = _gff.Root.GetResRef("OnTrapTriggered", new ResRef()),
                OnUnlock = _gff.Root.GetResRef("OnUnlock", new ResRef()),
                OnUserDefined = _gff.Root.GetResRef("OnUserDefined", new ResRef()),
                OpenLockDC = _gff.Root.GetUInt8("OpenLockDC", 0),
                OpenLockDiff = _gff.Root.GetUInt8("OpenLockDiff", 0),
                OpenLockDiffMod = _gff.Root.GetInt8("OpenLockDiffMod", 0),
                OpenState = _gff.Root.GetUInt8("OpenState", 0),
                PaletteID = _gff.Root.GetUInt8("PaletteID", 0),
                Plot = _gff.Root.GetUInt8("Plot", 0),
                PortraitId = _gff.Root.GetUInt16("PortraitId", 0),
                Ref = _gff.Root.GetUInt8("Ref", 0),
                Static = _gff.Root.GetUInt8("Static", 0),
                Tag = _gff.Root.GetString("Tag", ""),
                TemplateResRef = _gff.Root.GetResRef("TemplateResRef", new ResRef()),
                TrapDetectable = _gff.Root.GetUInt8("TrapDetectable", 0),
                TrapDetectDC = _gff.Root.GetUInt8("TrapDetectDC", 0),
                TrapDisarmable = _gff.Root.GetUInt8("TrapDisarmable", 0),
                TrapFlag = _gff.Root.GetUInt8("TrapFlag", 0),
                TrapOneShot = _gff.Root.GetUInt8("TrapOneShot", 0),
                TrapType = _gff.Root.GetUInt8("TrapType", 0),
                Will = _gff.Root.GetUInt8("Will", 0)
            };

            return utd;
        }
    }
}
