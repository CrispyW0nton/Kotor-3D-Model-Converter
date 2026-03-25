using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTD
{
    public class UTDDecompiler : IGFFCompiler
    {
        private UTD _utd;

        public UTDDecompiler(UTD utd)
        {
            _utd = utd;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            gff.Root.SetUInt8("AnimationState", _utd.AnimationState);
            gff.Root.SetUInt32("Appearance", _utd.Appearance);
            gff.Root.SetUInt8("AutoRemoveKey", _utd.AutoRemoveKey);
            gff.Root.SetUInt8("CloseLockDC", _utd.CloseLockDC);
            gff.Root.SetString("Comment", _utd.Comment);
            gff.Root.SetResRef("Conversation", _utd.Conversation);
            gff.Root.SetInt16("CurrentHP", _utd.CurrentHP);
            gff.Root.SetLocalizedString("Description", _utd.Description);
            gff.Root.SetUInt8("DisarmDC", _utd.DisarmDC);
            gff.Root.SetUInt32("Faction", _utd.Faction);
            gff.Root.SetUInt8("Fort", _utd.Fort);
            gff.Root.SetUInt8("GenericType", _utd.GenericType);
            gff.Root.SetUInt8("Hardness", _utd.Hardness);
            gff.Root.SetInt16("HP", _utd.HP);
            gff.Root.SetUInt8("Interruptable", _utd.Interruptable);
            gff.Root.SetString("KeyName", _utd.KeyName);
            gff.Root.SetUInt8("KeyRequired", _utd.KeyRequired);
            gff.Root.SetUInt16("LoadScreenID", _utd.LoadScreenID);
            gff.Root.SetUInt8("Lockable", _utd.Lockable);
            gff.Root.SetUInt8("Locked", _utd.Locked);
            gff.Root.SetLocalizedString("LocName", _utd.LocName);
            gff.Root.SetUInt8("Min1HP", _utd.Min1HP);
            gff.Root.SetUInt8("NotBlastable", _utd.NotBlastable);
            gff.Root.SetResRef("OnClick", _utd.OnClick);
            gff.Root.SetResRef("OnClosed", _utd.OnClosed);
            gff.Root.SetResRef("OnDamaged", _utd.OnDamaged);
            gff.Root.SetResRef("OnDeath", _utd.OnDeath);
            gff.Root.SetResRef("OnDisarm", _utd.OnDisarm);
            gff.Root.SetResRef("OnFailToOpen", _utd.OnFailToOpen);
            gff.Root.SetResRef("OnHeartbeat", _utd.OnHeartbeat);
            gff.Root.SetResRef("OnLock", _utd.OnLock);
            gff.Root.SetResRef("OnMeleeAttacked", _utd.OnMeleeAttacked);
            gff.Root.SetResRef("OnOpen", _utd.OnOpen);
            gff.Root.SetResRef("OnSpellCastAt", _utd.OnSpellCastAt);
            gff.Root.SetResRef("OnTrapTriggered", _utd.OnTrapTriggered);
            gff.Root.SetResRef("OnUnlock", _utd.OnUnlock);
            gff.Root.SetResRef("OnUserDefined", _utd.OnUserDefined);
            gff.Root.SetUInt8("OpenLockDC", _utd.OpenLockDC);
            gff.Root.SetUInt8("OpenLockDiff", _utd.OpenLockDiff);
            gff.Root.SetInt8("OpenLockDiffMod", _utd.OpenLockDiffMod);
            gff.Root.SetUInt8("OpenState", _utd.OpenState);
            gff.Root.SetUInt8("PaletteID", _utd.PaletteID);
            gff.Root.SetUInt8("Plot", _utd.Plot);
            gff.Root.SetUInt16("PortraitId", _utd.PortraitId);
            gff.Root.SetUInt8("Ref", _utd.Ref);
            gff.Root.SetUInt8("Static", _utd.Static);
            gff.Root.SetString("Tag", _utd.Tag);
            gff.Root.SetResRef("TemplateResRef", _utd.TemplateResRef);
            gff.Root.SetUInt8("TrapDetectable", _utd.TrapDetectable);
            gff.Root.SetUInt8("TrapDetectDC", _utd.TrapDetectDC);
            gff.Root.SetUInt8("TrapDisarmable", _utd.TrapDisarmable);
            gff.Root.SetUInt8("TrapFlag", _utd.TrapFlag);
            gff.Root.SetUInt8("TrapOneShot", _utd.TrapOneShot);
            gff.Root.SetUInt8("TrapType", _utd.TrapType);
            gff.Root.SetUInt8("Will", _utd.Will);

            return gff;
        }
    }
}
