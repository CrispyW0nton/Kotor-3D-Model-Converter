using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Patcher.Exceptions;
using Kotor.NET.Formats.KotorGFF;
using Kotor.NET.Patcher.Modifiers.ForGFF.Values;

namespace Kotor.NET.Patcher.Modifiers.ForGFF
{
    public class AddStructToList : IGFFModifier
    {
        internal GFFNavigator? _navigator;

        public object Value { get; set; }
        public string Path { get; set; }
        public Dictionary<int, IValue> ToStoreInMemory { get; set; }
        public List<IGFFModifier> SubFields { get; set; }

        public AddStructToList(object value, string path, Dictionary<int, IValue> toStoreInMemory, List<IGFFModifier> subFields)
        {
            Value = value;
            Path = path;
            ToStoreInMemory = toStoreInMemory;
            SubFields = subFields;
        }

        public void Apply(GFF target, IMemory memory, ILogger logger)
        {
            if (_navigator == null)
                _navigator = new GFFNavigator(target.Root);

            var nodes = Path.Split("\\");
            foreach (var node in nodes)
            {
                _navigator.NavigateTo(node);
            }

            var position = _navigator.Resolve();
            if (position is GFFList list)
            {
                list.Add((GFFStruct)Value);
                _navigator.NavigateTo((list.Count - 1).ToString());
            }
            else
            {
                throw new PatchingParserException("Specified path did not lead to a list.");
            }

            foreach (var toStoreInMemory in ToStoreInMemory)
            {
                var tokenID = toStoreInMemory.Key;
                var value = toStoreInMemory.Value.Resolve(memory, target);
                memory.Set2DAToken(tokenID, value);
            }

            foreach (var subfield in SubFields)
            {
                subfield.SetNavigator(_navigator);
                subfield.Apply(target, memory, logger);
            }
        }

        public void SetNavigator(GFFNavigator navigator)
        {
            _navigator = navigator;
        }
    }
}
