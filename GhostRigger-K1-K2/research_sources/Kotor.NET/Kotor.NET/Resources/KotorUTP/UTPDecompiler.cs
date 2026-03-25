using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTP;

public class UTPDecompiler : IGFFCompiler
{
    public UTP _utp;

    public UTPDecompiler(UTP utp)
    {
        _utp = utp;
    }

    public GFF CompileGFF()
    {
        var gff = new GFF();

        gff.Root.SetUInt8("AnimationState", _utp.AnimationState);
        gff.Root.SetUInt32("Appearance", _utp.Appearance);
        gff.Root.SetUInt8("AutoRemoveKey", _utp.AutoRemoveKey);
        gff.Root.SetUInt8("BodyBag", _utp.BodyBag);
        gff.Root.SetUInt8("CloseLockDC", _utp.CloseLockDC);
        gff.Root.SetString("Comment", _utp.Comment);
        gff.Root.SetResRef("Conversation", _utp.Conversation);
        gff.Root.SetInt16("CurrentHP", _utp.CurrentHP);
        gff.Root.SetLocalizedString("Description", _utp.Description);
        gff.Root.SetUInt8("DisarmDC", _utp.DisarmDC);
        gff.Root.SetUInt32("Faction", _utp.Faction);
        gff.Root.SetUInt8("Fort", _utp.Fort);
        gff.Root.SetUInt8("Hardness", _utp.Hardness);
        gff.Root.SetUInt8("HasInventory", _utp.HasInventory);
        gff.Root.SetInt16("HP", _utp.HP);
        gff.Root.SetUInt8("Interruptable", _utp.Interruptable);
        gff.Root.SetUInt8("IsComputer", _utp.IsComputer);
        gff.Root.SetString("KeyName", _utp.KeyName);
        gff.Root.SetUInt8("KeyRequired", _utp.KeyRequired);
        gff.Root.SetUInt8("Lockable", _utp.Lockable);
        gff.Root.SetUInt8("Locked", _utp.Locked);
        gff.Root.SetLocalizedString("LocName", _utp.LocName);
        gff.Root.SetUInt8("Min1HP", _utp.Min1HP);
        gff.Root.SetUInt8("NotBlastable", _utp.NotBlastable);
        gff.Root.SetResRef("OnClosed", _utp.OnClosed);
        gff.Root.SetResRef("OnDamaged", _utp.OnDamaged);
        gff.Root.SetResRef("OnDeath", _utp.OnDeath);
        gff.Root.SetResRef("OnDisarm", _utp.OnDisarm);
        gff.Root.SetResRef("OnEndDialogue", _utp.OnEndDialogue);
        gff.Root.SetResRef("OnFailToOpen", _utp.OnFailToOpen);
        gff.Root.SetResRef("OnHeartbeat", _utp.OnHeartbeat);
        gff.Root.SetResRef("OnInvDisturbed", _utp.OnInvDisturbed);
        gff.Root.SetResRef("OnLock", _utp.OnLock);
        gff.Root.SetResRef("OnMeleeAttacked", _utp.OnMeleeAttacked);
        gff.Root.SetResRef("OnOpen", _utp.OnOpen);
        gff.Root.SetResRef("OnSpellCastAt", _utp.OnSpellCastAt);
        gff.Root.SetResRef("OnTrapTriggered", _utp.OnTrapTriggered);
        gff.Root.SetResRef("OnUnlock", _utp.OnUnlock);
        gff.Root.SetResRef("OnUsed", _utp.OnUsed);
        gff.Root.SetResRef("OnUserDefined", _utp.OnUserDefined);
        gff.Root.SetUInt8("OpenLockDC", _utp.OpenLockDC);
        gff.Root.SetUInt8("OpenLockDiff", _utp.OpenLockDiff);
        gff.Root.SetInt8("OpenLockDiffMod", _utp.OpenLockDiffMod);
        gff.Root.SetUInt8("PaletteID", _utp.PaletteID);
        gff.Root.SetUInt8("PartyInteract", _utp.PartyInteract);
        gff.Root.SetUInt8("Plot", _utp.Plot);
        gff.Root.SetUInt16("PortraitId", _utp.PortraitId);
        gff.Root.SetUInt8("Ref", _utp.Ref);
        gff.Root.SetUInt8("Static", _utp.Static);
        gff.Root.SetString("Tag", _utp.Tag);
        gff.Root.SetResRef("TemplateResRef", _utp.TemplateResRef);
        gff.Root.SetUInt8("TrapDetectable", _utp.TrapDetectable);
        gff.Root.SetUInt8("TrapDetectDC", _utp.TrapDetectDC);
        gff.Root.SetUInt8("TrapDisarmable", _utp.TrapDisarmable);
        gff.Root.SetUInt8("TrapFlag", _utp.TrapFlag);
        gff.Root.SetUInt8("TrapOneShot", _utp.TrapOneShot);
        gff.Root.SetUInt8("TrapType", _utp.TrapType);
        gff.Root.SetUInt8("Type", _utp.Type);
        gff.Root.SetUInt8("Useable", _utp.Useable);
        gff.Root.SetUInt8("Will", _utp.Will);
        var itemList = gff.Root.SetList("ItemList", new());

        foreach (var item in _utp.Inventory)
        {
            itemList.Add(new GFFStruct
            {
                ["InventoryRes"] = item.ResRef
            });
        }

        return gff;
    }
}
