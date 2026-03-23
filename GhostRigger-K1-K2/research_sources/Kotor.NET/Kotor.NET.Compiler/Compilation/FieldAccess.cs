using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Scripting.Compilation
{
    public class FieldAccess
    {
        public List<string> Identifiers { get; set; }

        public FieldAccess(string identifier)
        {
            Identifiers = new() { identifier };
        }

        public FieldAccess(string identifier1, string identifier2)
        {
            Identifiers = new() { identifier1, identifier2 };
        }

        public FieldAccess(FieldAccess fieldAccess, string identifier)
        {
            Identifiers = fieldAccess.Identifiers;
            Identifiers.Add(identifier);
        }
    }
}
