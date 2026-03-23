using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Patcher.Exceptions;
using Kotor.NET.Extensions;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Patcher.Modifiers.ForGFF
{
    public class ModifyFieldGFFModifier : IModifier<GFF>
    {
        public string Label { get; }
        public string Directive { get; }
        public string[] Path { get; }
        public string Value { get; }

        public ModifyFieldGFFModifier(string label, string directive, string[] path, string value)
        {
            Label = label;
            Directive = directive;
            Path = path;
            Value = value;
        }

        public void Apply(GFF target, IMemory memory, ILogger logger)
        {
            var navigator = new GFFNavigator(target);
            foreach (var node in Path)
            {
                navigator.NavigateTo(node);
            }

            var finalNode = navigator.Resolve();
            if (finalNode is GFFStruct gffStruct)
            {
                var field = gffStruct.Get(Label);
                var ttype = field.Value.GetType();

                if (field.Type == GFFFieldType.Int8)
                {
                    field.Value = Convert.ToSByte(Value);
                }
                else if (field.Type == GFFFieldType.UInt8)
                {
                    field.Value = Convert.ToByte(Value);
                }
                else if (field.Type == GFFFieldType.Int16)
                {
                    field.Value = Convert.ToInt16(Value);
                }
                else if (field.Type == GFFFieldType.UInt16)
                {
                    field.Value = Convert.ToUInt16(Value);
                }
                else if (field.Type == GFFFieldType.Int32)
                {
                    field.Value = Convert.ToInt32(Value);
                }
                else if (field.Type == GFFFieldType.UInt32)
                {
                    field.Value = Convert.ToUInt32(Value);
                }
                else if (field.Type == GFFFieldType.Int64)
                {
                    field.Value = Convert.ToInt64(Value);
                }
                else if (field.Type == GFFFieldType.UInt64)
                {
                    field.Value = Convert.ToUInt64(Value);
                }
                else if (field.Type == GFFFieldType.Single)
                {
                    field.Value = Convert.ToSingle(Value);
                }
                else if (field.Type == GFFFieldType.Double)
                {
                    field.Value = Convert.ToDouble(Value);
                }
                else if (field.Type == GFFFieldType.ResRef)
                {
                    field.Value = new ResRef(Value);
                }
                else if (field.Type == GFFFieldType.String)
                {
                    field.Value = Value;
                }
                else if (field.Type == GFFFieldType.Vector3)
                {
                    var floats = Value.Split("|").Where(x => x.IsSingle()).Select(x => Convert.ToSingle(x)).ToArray();

                    if (floats.Length == 3)
                    {
                        field.Value = new Vector3(floats[0], floats[1], floats[2]);
                    }
                    else
                    {
                        throw new PatchingParserException("Vector3 was incorrectly formatted.");
                    }
                }
                else if (field.Type == GFFFieldType.Vector4)
                {
                    var floats = Value.Split("|").Where(x => x.IsSingle()).Select(x => Convert.ToSingle(x)).ToArray();

                    if (floats.Length == 4)
                    {
                        field.Value = new Vector4(floats[0], floats[1], floats[2], floats[3]);
                    }
                    else
                    {
                        throw new PatchingParserException("Vector4 was incorrectly formatted.");
                    }
                }
                else if (field.Type == GFFFieldType.LocalizedString)
                {
                    var locstring = (LocalizedString)field.Value;
                    if (Directive == "stringref")
                    {
                        locstring.StringRef = Convert.ToInt32(Value);
                    }
                    else if (Directive.Contains("(lang"))
                    {
                        var substringID = Convert.ToInt32(Label.Substring(Label.IndexOf("(lang")+5, Label.IndexOf(")")));
                        locstring.Set(substringID, Value);
                    }
                    else
                    {
                        throw new PatchingParserException("Unknown or no directive specified for locstring modifier.");
                    }
                }
            }
            else
            {
                throw new PatchingParserException("Trying to add a field to a list.");
            }
        }
    }

    //public class ModifyFieldGFFModifier : IModifier<GFF>
    //{
    //    public string Label { get; }
    //    public string[] Path { get; }
    //    public string Value { get; }

    //    public ModifyFieldGFFModifier(string label, string[] path, string value)
    //    {
    //        Label = label;
    //        Path = path;
    //        Value = value;
    //    }

    //    public void Apply(GFF target, IMemory memory, ILogger logger)
    //    {
    //        var navigator = new GFFNavigator(target);
    //        foreach (var node in Path)
    //        {
    //            navigator.NavigateTo(node);
    //        }

    //        var finalNode = navigator.Resolve();
    //        if (finalNode is GFFStruct gffStruct)
    //        {
    //            gffStruct.Set(Label, Value);
    //        }
    //        else
    //        {
    //            throw new PatchingParserException("Trying to add a field to a list.");
    //        }
    //    }
    //}
}
